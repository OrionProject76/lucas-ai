# core/voice_commands.py — commandes vocales d'arrêt du mode conversation
# (BRIEF_MODE_VOCAL_CONTINU_MOBILE.md, suite du 10/08/2026).
#
# Remplace le minuteur de 60s comme mécanisme PRINCIPAL d'extinction du
# mode conversation (static/js/conversation_mode.js) : Cyril demande
# explicitement d'arrêter, à voix haute, plutôt que d'attendre un silence.
# Un minuteur de sécurité, bien plus long, reste en filet (voir
# conversation_mode.js) au cas où la phrase ne serait pas reconnue.
#
# Même doctrine que core/router.py (is_sensitive) : une comparaison
# déterministe sur texte normalisé (core/text_utils.normalize), pas un
# appel LLM. Se tromper ici coûte un clic sur le bouton d'arrêt, jamais
# une fuite — donc pas la même exigence de fiabilité que is_sensitive,
# mais la même méthode, pour la même raison : reproductible, testable,
# indépendante du modèle.

from __future__ import annotations

from collections.abc import Sequence

from core.text_utils import normalize

# Préambules courants avant une commande ("Luca's, stop", "OK, arrête-toi")
# — retirés avant comparaison pour ne pas exiger une phrase isolée. Liste
# volontairement courte : chaque ajout doit correspondre à un usage réel,
# pas à une anticipation.
_LEADING_FILLERS = ("luca's", "lucas", "ok", "okay", "d'accord", "bon", "voila")

# Phrases complètes (normalisées) qui déclenchent l'arrêt. Comparaison
# EXACTE après normalisation/retrait des préambules — pas une recherche de
# sous-chaîne : "stop" ne doit jamais matcher au milieu d'une phrase sur
# un tout autre sujet ("qu'est-ce qui a stoppé le service ?").
STOP_PHRASES: frozenset[str] = frozenset(
    normalize(phrase)
    for phrase in (
        "stop",
        "arrete",
        "arrete-toi",
        "arrete toi",
        "tu peux t'eteindre",
        "eteins-toi",
        "eteins toi",
        "coupe le micro",
        "coupe-toi",
        "termine la conversation",
        "fin de la conversation",
        "desactive le mode conversation",
    )
)


def is_stop_command(text: str) -> bool:
    """
    Vrai si `text` (la transcription d'un tour) est une commande d'arrêt
    du mode conversation, pas un message normal destiné à Luca's.

    Comparaison sur la phrase ENTIÈRE (après normalisation, découpage en
    mots et retrait d'un éventuel préambule court) — jamais une recherche
    de sous-chaîne, pour ne pas confondre "stop" prononcé comme commande
    avec le même mot employé dans une phrase ordinaire.
    """
    # La virgule d'un préambule ("Luca's, stop") survit à normalize() —
    # seuls les espaces/tirets typographiques (Zs/Pd) y sont repliés, pas
    # la ponctuation ordinaire, à raison : d'autres comparaisons dans le
    # projet en ont besoin. Le découpage en mots l'absorbe ici sans avoir
    # à y toucher.
    words = normalize(text).replace(",", " ").split()
    while words and words[0] in _LEADING_FILLERS:
        words.pop(0)
    return " ".join(words) in STOP_PHRASES


# ── Mot d'adressage du mode mains libres (13/08/2026) ──────────────────
#
# ⚠️ Changement de COMPORTEMENT, pas un filtre de plus : en mode
# conversation, Luca's ne répond plus à tout ce qu'elle entend, seulement
# à ce qui lui est adressé. Décidé par Cyril après une conversation
# fantôme réelle où la télévision a tenu plusieurs tours à sa place
# (ROADMAP.md §5.98).
#
# Pourquoi ici et pas un seuil de plus : aucun score de Whisper ne
# distingue deux voix humaines. La voix de la TV est mesurée à 0,977 de
# confiance, celle de Cyril à 0,997 — le seuil qui exclurait l'une
# exclurait l'autre. Ce qui les sépare n'est pas la qualité du signal,
# c'est l'intention : l'une s'adresse à Luca's, l'autre non.
#
# Le mot est comparé après `normalize()` (accents, casse) et retrait de la
# ponctuation : c'est Whisper qui écrit, et « Luca's » lui revient tantôt
# « Lucas », tantôt « Luca », parfois « Lukas ».


def _leading_words(text: str) -> list[str]:
    """Mots normalisés du texte, ponctuation d'adressage absorbée."""
    cleaned = normalize(text)
    for sign in (",", ".", "!", "?", ":", ";", "'", "’"):
        cleaned = cleaned.replace(sign, " ")
    return cleaned.split()


def has_wake_word(text: str, wake_words: Sequence[str]) -> bool:
    """
    Vrai si `text` COMMENCE par le mot d'adressage.

    Uniquement en tête : « je parlais de Lucas à mon frère » ne doit pas
    valider un tour. C'est la même exigence de position que
    `is_stop_command`, pour la même raison — une recherche de
    sous-chaîne transformerait toute mention du nom en interpellation.
    """
    words = _leading_words(text)
    if not words:
        return False
    return words[0] in {normalize(w) for w in wake_words}


def strip_wake_word(text: str, wake_words: Sequence[str]) -> str:
    """
    Retire le mot d'adressage en tête, en gardant le texte D'ORIGINE.

    Travaille sur le texte brut plutôt que sur sa version normalisée : ce
    qui part au modèle doit garder ses accents et sa ponctuation. Seul le
    repérage se fait sur la forme normalisée.

    Rendu vide si le tour ne contenait QUE le mot d'adressage — appeler
    Luca's sans rien dire n'est pas une question, et l'appelant doit
    pouvoir le voir.
    """
    if not has_wake_word(text, wake_words):
        return text.strip()
    # Le premier mot du texte brut correspond au mot d'adressage repéré :
    # on le coupe là où il finit, puis on absorbe la ponctuation qui le
    # sépare de la suite (« Luca's, quelle heure est-il ? »).
    stripped = text.strip()
    parts = stripped.split(maxsplit=1)
    rest = parts[1] if len(parts) > 1 else ""
    return rest.lstrip(" ,.!?:;'’")
