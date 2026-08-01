# core/intent.py — quelle source consulter avant de répondre
#
# ── Pourquoi ce module existe ─────────────────────────────────────────
#
# Le déclenchement de la vision et du RAG reposait sur deux listes de
# mots-clés (router.KEYWORDS_VISION, router.KEYWORDS_RAG). Mesuré sur un
# corpus de formulations réellement tapées par Cyril : **50 % de réussite**.
# Deux défauts distincts, dont un seul se répare :
#
#   1. COLLISION. « Je voudrais une synthèse rapide d'un document sur mon
#      écran » déclenchait les DEUX. Le bloc RAG étant injecté après le
#      bloc vision — donc plus près de la question — le LLM suivait le RAG
#      et ignorait ce qui avait été lu à l'écran.
#
#   2. COUVERTURE. « c'est écrit quoi ? », « montre-moi ce qu'il y a marqué
#      là », « j'ai un message d'erreur, aide-moi » ne contiennent AUCUN
#      mot désignant l'écran. Aucune liste de mots-clés ne les attrapera
#      jamais. Ce n'est pas un oubli, c'est une limite de la méthode.
#
# Un classifieur local répond aux deux à la fois : il rend UN seul label,
# donc la collision devient structurellement impossible, et il lit la
# phrase au lieu d'y chercher des sous-chaînes.
#
# ── Ce que ce module ne fait PAS ──────────────────────────────────────
#
# ⚠️ Il ne décide JAMAIS si une donnée est sensible. Cette décision-là
# reste aux mots-clés déterministes de router.is_sensitive(), et il faut
# que ça le reste : se tromper ici coûte une réponse un peu moins bonne,
# se tromper là-bas envoie un relevé bancaire chez OpenAI. Un modèle est
# le bon outil pour la première question, le mauvais pour la seconde.
# Voir CLAUDE.md règle 3.
#
# ── Coût ──────────────────────────────────────────────────────────────
#
# 0,14 s par message (qwen2.5:7b, temperature 0, 5 tokens générés). Ce
# chiffre n'a été atteignable qu'après le passage de « localhost » à
# 127.0.0.1, qui coûtait 2,05 s de timeout IPv6 par appel — voir config.py.

from __future__ import annotations

import re
from dataclasses import dataclass

from config import (
    INTENT_CLASSIFIER_ENABLED,
    INTENT_MODEL,
    INTENT_TIMEOUT_SECONDS,
    OLLAMA_URL,
)

# Les trois seules réponses acceptées. Toute autre sortie du modèle est
# traitée comme un échec et bascule sur les mots-clés — on ne devine pas
# ce qu'il a voulu dire.
SCREEN = "ECRAN"
DOCUMENTS = "DOCUMENTS"
NEITHER = "AUCUN"
LABELS = (SCREEN, DOCUMENTS, NEITHER)

# ⚠️ Sans accents ni apostrophes courbes, volontairement. Le prompt doit
# rester lisible pour un modèle 7b ; les questions de Cyril, elles, sont
# normalisées en amont par text_utils quand le repli mots-clés s'applique.
CLASSIFIER_PROMPT = """Tu classes la question d'un utilisateur pour savoir quelle source d'information consulter avant de lui repondre.

ECRAN : la question porte sur ce qui est affiche MAINTENANT sur son ecran.
  Indices : il dit "ca", "ce truc", "la", "ce document", "cette fenetre",
  "affiche", "ouvert", "a l'ecran" ; il parle d'une erreur ou d'un message
  qu'il a sous les yeux ; sa phrase n'a de sens que s'il regarde quelque chose.
  Exemples : "c'est ecrit quoi ?" / "analyse ce document ouvert" /
  "j'ai un message d'erreur, aide-moi" / "montre-moi ce qu'il y a marque la"

DOCUMENTS : la question porte sur des fichiers personnels ARCHIVES, qu'il
  faut aller rechercher. Il nomme le document ou son sujet, sans rien montrer.
  Exemples : "resume mon rapport annuel" / "que dit le document sur les conges"

AUCUN : ni l'un ni l'autre. Culture generale, conversation, calcul, meteo.
  Exemples : "quelle heure il est" / "explique-moi la photosynthese"

Regle de depart : un demonstratif ("ce", "cette", "ca", "la") sans nom de
fichier precis designe l'ecran, pas une archive.
En cas de doute entre ECRAN et DOCUMENTS, reponds ECRAN.

PIEGE : certains verbes de perception sont idiomatiques et ne designent
rien de visible. "regarde si tu peux m'aider", "vois si c'est possible",
"dis-moi voir" = AUCUN. Le verbe seul ne suffit pas : il faut un objet
visible ("regarde MON ECRAN", "regarde CETTE erreur").

Reponds par UN SEUL MOT : ECRAN, DOCUMENTS ou AUCUN."""


# ── Garde déictique ───────────────────────────────────────────────────
#
# Un motif résiste au classifieur : « analyse ce document ouvert »,
# « résume ce document » partent en DOCUMENTS. Vérifié sur les trois
# modèles installés — qwen2.5:7b, llama3.1:8b, gemma4 — tous les trois
# s'y trompent de la même façon. Renforcer le prompt n'y change
# strictement rien (testé : résultats identiques au caractère près). Le
# mot « document » est un attracteur plus fort que la consigne.
#
# Ce n'est pas un mot-clé de plus, et c'est ce qui justifie de l'écrire
# en dur : un DÉMONSTRATIF est un marqueur déictique, il désigne
# grammaticalement ce qui est présent dans la situation partagée. « ce
# document » est celui qu'on voit tous les deux ; « mon rapport annuel »
# ou « le document sur les congés » nomment un absent qu'il faut aller
# chercher. La règle porte sur la grammaire, pas sur le vocabulaire —
# elle vaut donc pour « ce truc », « cette page », « ces fichiers », que
# personne n'a besoin d'énumérer.
#
# ⚠️ « ce que » et « ce qui » sont exclus : pronom relatif, pas
# démonstratif. Sans cette exclusion, « rappelle-moi CE QUE contient mon
# contrat d'assurance » — une vraie question d'archive — basculerait à
# tort vers l'écran. Vérifié : zéro faux positif sur le corpus.
DEICTIC = re.compile(r"\b(ce|cet|cette|ces)\s+(?!que\b|qui\b|qu)")


def _is_deictic(question: str) -> bool:
    from core.text_utils import normalize

    return bool(DEICTIC.search(normalize(question)))


@dataclass(frozen=True)
class Intent:
    """
    Quelle source consulter avant de répondre.

    Les deux drapeaux sont mutuellement exclusifs par construction : le
    classifieur rend un label unique. C'est ce qui supprime la collision
    RAG/vision à la racine, plutôt que de l'arbitrer après coup.
    """

    needs_screen: bool
    needs_documents: bool
    source: str  # "llm" quand le classifieur a tranché, "keywords" en repli

    @property
    def is_fallback(self) -> bool:
        return self.source == "keywords"


def _ask_classifier(question: str) -> str | None:
    """
    Interroge le modèle local. Retourne un label, ou None si quoi que ce
    soit a échoué — Ollama absent, délai dépassé, réponse inattendue.

    Aucune exception ne remonte : un classifieur indisponible doit
    dégrader le déclenchement, jamais empêcher Luca's de répondre.
    """
    try:
        from core.ollama_client import post_chat

        response = post_chat(
            OLLAMA_URL,
            {
                "model": INTENT_MODEL,
                "messages": [
                    {"role": "system", "content": CLASSIFIER_PROMPT},
                    {"role": "user", "content": question},
                ],
                "stream": False,
                # temperature 0 : la même question doit donner la même
                # réponse d'une fois sur l'autre, sinon le corpus de test
                # ne mesure rien.
                "options": {"temperature": 0, "num_predict": 5},
                "keep_alive": "30m",
            },
            timeout=INTENT_TIMEOUT_SECONDS,
        )
        raw = response.json()["message"]["content"]
    except Exception:  # noqa: BLE001 — voir docstring
        return None

    # Le modèle ajoute parfois un point ou une majuscule accentuée.
    answer = raw.strip().upper().strip(".").strip()
    return answer if answer in LABELS else None


# ⚠️ Ce cache n'est pas une optimisation, il est nécessaire à la
# correction du coût annoncé. Un même message traverse classify() jusqu'à
# quatre fois : route() consulte les deux axes, puis
# OrionCore._build_messages() les reconsulte pour décider quels blocs
# injecter. Sans cache, les 0,14 s deviendraient 0,56 s.
# Le résultat est déterministe (temperature 0), donc le cache est exact.
_CACHE: dict[str, Intent] = {}
_CACHE_MAX = 64


def classify(question: str) -> Intent:
    """
    Décide quelle source consulter pour cette question.

    Bascule sur les mots-clés si le classifieur est désactivé ou
    indisponible. Le repli est volontairement l'ancien comportement à
    l'identique : il vaut mieux 50 % de couverture qu'aucune réponse.
    """
    cached = _CACHE.get(question)
    if cached is not None:
        return cached

    if INTENT_CLASSIFIER_ENABLED and question.strip():
        label = _ask_classifier(question)
        if label is not None:
            # La garde déictique ne corrige QUE le sens DOCUMENTS → ECRAN.
            # Elle ne peut jamais faire naître une consultation de
            # documents, ni transformer un AUCUN en déclenchement : au
            # pire elle fait regarder l'écran, ce qui reste local et
            # visible dans la réponse.
            if label == DOCUMENTS and _is_deictic(question):
                label = SCREEN

            intent = Intent(
                needs_screen=label == SCREEN,
                needs_documents=label == DOCUMENTS,
                source="llm",
            )
            # Seuls les verdicts du classifieur sont mémorisés. Mettre un
            # repli en cache figerait une panne passagère d'Ollama sur
            # cette question pour toute la session.
            if len(_CACHE) >= _CACHE_MAX:
                _CACHE.clear()
            _CACHE[question] = intent
            return intent

    return _classify_by_keywords(question)


def _classify_by_keywords(question: str) -> Intent:
    """
    Repli sur les listes de mots-clés historiques.

    ⚠️ La priorité ÉCRAN y est appliquée explicitement, alors que
    l'ancien code laissait les deux drapeaux à True simultanément. Même
    en repli, la collision ne doit pas revenir.

    Pourquoi l'écran gagne l'égalité : ce qu'il montre est vérifiable —
    l'OCR a trouvé du texte ou non, et le bloc injecté le dit. Le RAG n'a
    pas cet aveu ; quand il se trompe, il empoisonne silencieusement la
    réponse avec du contenu plausible mais hors sujet.
    """
    from core.router import KEYWORDS_RAG, KEYWORDS_VISION
    from core.text_utils import contains_any

    screen = contains_any(question, KEYWORDS_VISION)
    documents = contains_any(question, KEYWORDS_RAG) and not screen
    return Intent(needs_screen=screen, needs_documents=documents, source="keywords")
