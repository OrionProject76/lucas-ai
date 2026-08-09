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
