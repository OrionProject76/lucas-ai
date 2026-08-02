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
    CONTEXT_MAX_CHARS,
    CONTEXT_TURNS,
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


# ── Ellipse : la question qui continue la précédente ──────────────────
#
# « Et pour 2024 ? » n'a pas de sujet propre. Mesuré selon l'échange qui
# la précède : DOCUMENTS après « mon salaire de juillet 2025 », mais
# AUCUN après « mon relevé de carrière » et après « résume-moi mon CV » —
# ces deux-là n'ont aucune dimension temporelle explicite, et le lien ne
# se fait pas. Pire, le verdict bascule sur un mot de la RÉPONSE
# précédente : « trimestres cotisés » donne AUCUN, « trimestres cotisés
# depuis 1995 » donne ECRAN.
#
# Le prompt engineering est épuisé sur ce cas : une consigne « suite de
# conversation » dégrade de 4/5 à 2/5 en poussant tout vers ECRAN, et
# doubler le contexte ne change rien (vérifié à 2 et 4 tours).
#
# D'où une règle de GRAMMAIRE, comme la garde déictique. Une ellipse ne
# change pas de sujet — c'est ce qui la définit. Elle hérite donc du
# verdict de la question précédente au lieu d'être reclassée dans le
# vide.
ELLIPSIS_START = re.compile(r"^et\b")

# Borne de longueur : au-delà, la phrase a un sujet propre et n'est plus
# une ellipse. « Et si on parlait d'autre chose ? » ne doit pas hériter.
ELLIPSIS_MAX_WORDS = 6


def is_elliptical(question: str) -> bool:
    """La question continue-t-elle la précédente sans sujet propre ?"""
    from core.text_utils import normalize

    plain = normalize(question).strip().strip("?!.… ")
    if not ELLIPSIS_START.match(plain):
        return False
    return 0 < len(plain.split()) <= ELLIPSIS_MAX_WORDS


def previous_question(context: str) -> str:
    """
    Dernière question de Cyril dans le contexte, ou chaîne vide.

    Analyse le format produit par format_context() — seul producteur de
    ces chaînes, juste au-dessus dans ce fichier. Passer la question par
    un paramètre séparé aurait exigé de la faire traverser route(),
    should_use_rag(), should_use_vision() et l'UI pour un seul usage.
    """
    lignes = [
        ligne[len("Cyril :"):].strip()
        for ligne in context.splitlines()
        if ligne.startswith("Cyril :")
    ]
    return lignes[-1] if lignes else ""


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


def format_context(history) -> str:
    """
    Résume le dernier échange, pour donner au classifieur de quoi
    interpréter une question elliptique.

    ⚠️ Le DERNIER échange seulement. Observé : « Et en décembre 2025 ? »
    après une question sur un bulletin de paie était classée AUCUN — la
    phrase, seule, ne parle ni d'écran ni de documents. Elle n'a de sens
    que par rapport à ce qui précède.

    Volontairement court et tronqué : le classifieur doit rendre un mot
    en 0,14 s, pas relire la conversation. Une réponse entière ferait
    basculer la décision sur son contenu plutôt que sur la question.

    `history` est une liste de (rôle, texte) telle que la rend
    MemoryManager.load_history(), la plus récente en dernier.
    """
    if not history:
        return ""

    derniers = [
        (role, texte) for role, texte in history[-CONTEXT_TURNS:] if texte.strip()
    ]
    if not derniers:
        return ""

    lignes = []
    for role, texte in derniers:
        qui = "Cyril" if role == "user" else "Toi"
        lignes.append(f"{qui} : {texte.strip()[:CONTEXT_MAX_CHARS]}")
    return "\n".join(lignes)


def _ask_classifier(question: str, context: str = "") -> str | None:
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
                    *(
                        [{
                            "role": "system",
                            "content": (
                                "Échange précédent, pour interpréter une "
                                "question elliptique. Classe la QUESTION "
                                "qui suit, pas cet échange :\n" + context
                            ),
                        }]
                        if context
                        else []
                    ),
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
#
# ⚠️ La clé inclut le CONTEXTE. « Et en décembre 2025 ? » ne se classe
# pas pareil selon ce qui précède : garder le verdict d'un autre contexte
# rendrait la réponse fausse et impossible à comprendre.
_CACHE: dict[tuple[str, str], Intent] = {}
_CACHE_MAX = 64


def classify(question: str, context: str = "", _inherit: bool = True) -> Intent:
    """
    Décide quelle source consulter pour cette question.

    `context` est le dernier échange, mis en forme par format_context().
    Il sert aux questions elliptiques — « Et en décembre 2025 ? » n'a de
    sens que par rapport à ce qui précède, et était classée AUCUN.

    Une ellipse HÉRITE du verdict de la question précédente plutôt que
    d'être reclassée : elle n'a pas de sujet propre, et la reclasser
    donnait AUCUN une fois sur deux. `_inherit` est un garde-fou interne
    contre la récursion, à ne pas passer depuis l'extérieur.

    Bascule sur les mots-clés si le classifieur est désactivé ou
    indisponible. Le repli est volontairement l'ancien comportement à
    l'identique : il vaut mieux 50 % de couverture qu'aucune réponse.
    """
    cle = (context, question)
    cached = _CACHE.get(cle)
    if cached is not None:
        return cached

    # ⚠️ HÉRITAGE — une ellipse ne change pas de sujet, c'est ce qui la
    # définit. La reclasser dans le vide donnait AUCUN une fois sur deux.
    # `_inherit=False` sur l'appel récursif : si la question précédente
    # est elle-même une ellipse, on ne remonte pas la chaîne à l'infini.
    if _inherit and context and is_elliptical(question):
        precedente = previous_question(context)
        if precedente and precedente != question:
            herite = classify(precedente, "", _inherit=False)
            # Un repli mots-clés ne s'hérite pas : il vaut 50 % de
            # couverture, et le propager doublerait ses erreurs.
            if not herite.is_fallback:
                intent = Intent(
                    needs_screen=herite.needs_screen,
                    needs_documents=herite.needs_documents,
                    source="inherited",
                )
                if len(_CACHE) >= _CACHE_MAX:
                    _CACHE.clear()
                _CACHE[cle] = intent
                return intent

    if INTENT_CLASSIFIER_ENABLED and question.strip():
        label = _ask_classifier(question, context)
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
            _CACHE[cle] = intent
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
