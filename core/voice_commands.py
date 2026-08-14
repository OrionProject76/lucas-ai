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

import re
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


# Mots d'accompagnement retirés AVEC le nom, et seulement quand ils lui
# sont collés : « dis-moi Luca, il est quelle heure ? » doit arriver au
# modèle comme « il est quelle heure ? ».
#
# ⚠️ Uniquement adjacents au mot d'adressage, jamais partout dans la
# phrase : « dis » et « moi » portent du sens ailleurs (« ce que moi j'en
# pense »). Le « s » est là pour absorber la forme « Luca's » écrite par
# Whisper, dont le découpage en mots isole le s.
_WAKE_FILLERS = frozenset(
    {"dis", "moi", "he", "eh", "hey", "ok", "okay", "bon", "alors", "s", "stp"}
)

# Mots du texte, positions comprises : le repérage se fait sur la forme
# normalisée, la découpe sur le texte D'ORIGINE — ce qui part au modèle
# doit garder ses accents et sa ponctuation.
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _words_with_spans(text: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), normalize(m.group())) for m in _WORD_RE.finditer(text)]


def has_wake_word(text: str, wake_words: Sequence[str]) -> bool:
    """
    Vrai si le mot d'adressage apparaît QUELQUE PART dans `text`.

    ⚠️ N'importe où, pas seulement en tête — choix de Cyril du 13/08/2026
    (ROADMAP.md §5.98). À l'oral, l'interpellation se place aussi bien au
    début (« Luca, quelle heure est-il ? ») qu'au milieu (« dis-moi Luca,
    il est quelle heure ? ») ou à la fin (« il est quelle heure Luca ? »).
    Exiger la tête aurait fait rejeter deux formulations sur trois.

    Comparaison sur des MOTS ENTIERS, jamais une sous-chaîne : « lucarne »
    ou « élucubration » contiennent les mêmes lettres sans interpeller
    personne.

    ⚠️ Conséquence assumée de la détection n'importe où : « je parlais de
    Lucas à mon frère » valide désormais un tour. Le compromis est voulu —
    manquer une vraie interpellation coûte plus cher, en mains libres,
    qu'accepter une phrase où Cyril prononce ce nom sans s'adresser à
    elle. Un mot d'adressage reste un filtre d'intention, pas une preuve.
    """
    targets = {normalize(w) for w in wake_words}
    return any(word in targets for _, _, word in _words_with_spans(text))


def strip_wake_word(text: str, wake_words: Sequence[str]) -> str:
    """
    Retire le mot d'adressage, où qu'il soit, et ce qui l'accompagne.

    Le nom a servi à décider qu'on écoutait ; il n'apporte rien à la
    question elle-même, et le répéter à chaque tour polluerait le prompt.

    Rendu vide si le tour ne contenait QUE l'appel — appeler Luca's sans
    rien dire d'autre n'est pas une question, et l'appelant doit pouvoir
    le voir.
    """
    words = _words_with_spans(text)
    targets = {normalize(w) for w in wake_words}
    index = next((i for i, (_, _, w) in enumerate(words) if w in targets), None)
    if index is None:
        return text.strip()

    # Étendu aux mots d'accompagnement COLLÉS au nom, des deux côtés.
    first, last = index, index
    while first > 0 and words[first - 1][2] in _WAKE_FILLERS:
        first -= 1
    while last + 1 < len(words) and words[last + 1][2] in _WAKE_FILLERS:
        last += 1

    cut = text[: words[first][0]] + " " + text[words[last][1] :]
    # La ponctuation qui séparait l'appel du reste devient orpheline
    # (« Luca, quelle heure ? » laisse une virgule en tête) — retirée
    # seulement en début, jamais en fin : le « ? » final appartient à la
    # question, pas à l'appel.
    cleaned = " ".join(cut.split())
    return cleaned.lstrip(" ,.!?:;'’-").strip()
