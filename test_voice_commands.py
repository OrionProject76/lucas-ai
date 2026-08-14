# test_voice_commands.py — commandes vocales d'arrêt du mode conversation

from __future__ import annotations

import pytest

from core.voice_commands import is_stop_command


@pytest.mark.parametrize(
    "text",
    [
        "stop",
        "Stop",
        "STOP",
        "arrête",
        "arrête-toi",
        "arrête toi",
        "tu peux t'éteindre",
        "éteins-toi",
        "éteins toi",
        "coupe le micro",
        "coupe-toi",
        "termine la conversation",
        "fin de la conversation",
        "désactive le mode conversation",
    ],
)
def test_recognizes_the_exact_stop_phrases(text: str) -> None:
    assert is_stop_command(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "Luca's, stop",
        "OK stop",
        "d'accord, arrête-toi",
        "bon, éteins-toi",
        "Lucas stop",
    ],
)
def test_recognizes_stop_phrases_with_a_short_preamble(text: str) -> None:
    assert is_stop_command(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "quel temps fait-il ?",
        "raconte-moi une blague",
        "qu'est-ce qui a stoppé le service la nuit dernière ?",
        "arrête de me poser cette question",
        "",
        "stop et redémarre le calcul",
    ],
)
def test_does_not_match_ordinary_sentences(text: str) -> None:
    assert is_stop_command(text) is False


# ── Mot d'adressage du mode mains libres (13/08/2026, ROADMAP.md §5.98) ──
#
# Changement de comportement, pas un filtre : Luca's ne répond plus qu'à ce
# qui lui est adressé quand le micro écoute en continu. Le corpus ci-dessous
# est celui des formes que Whisper produit réellement pour « Luca's » — la
# graphie vient du modèle, jamais de Cyril.

import pytest

from config import CONVERSATION_WAKE_WORDS
from core.voice_commands import has_wake_word, strip_wake_word


@pytest.mark.parametrize(
    "phrase",
    [
        # ── En TÊTE ──
        # La forme PARLÉE de référence, choisie par Cyril le 13/08/2026 :
        # « Luca » seul, plus naturel à dire que « Luca's ».
        "Luca, quelle heure est-il ?",
        "Luca quelle heure est-il ?",
        "luca raconte moi une blague",
        # ── Au MILIEU ──
        "dis-moi Luca, il est quelle heure ?",
        "alors Luca, tu en penses quoi ?",
        # ── En FIN ──
        "il est quelle heure Luca ?",
        "tu m'entends Luca",
        # ── Ce que Whisper en fait réellement (le français ajoute le s) ──
        "Luca's, quelle heure est-il ?",
        "Lucas quelle heure est-il ?",
        "Lucas, quelle heure est-il ?",
        "lucas raconte moi une blague",
        "Luka, tu m'entends ?",
        "Lukas ! Réveille-toi.",
        "LUCAS, allume la lumière",
    ],
)
def test_addressed_turns_are_recognised(phrase: str) -> None:
    """Début, milieu ou fin : à l'oral, l'interpellation se place partout."""
    assert has_wake_word(phrase, CONVERSATION_WAKE_WORDS)


@pytest.mark.parametrize(
    "phrase",
    [
        # Le cas réel du 13/08 : la télévision, en anglais
        "Thank you. Good night.",
        "And now, the weather forecast for tomorrow morning.",
        # La télévision en français — la langue ne suffit pas, d'où ce test
        "Et maintenant la météo de demain matin sur toute la région.",
        # La vraie voix de Cyril, en français, mais sans l'appeler :
        # rejetée aussi, et c'est tout l'objet du changement.
        "Quelle heure est-il ?",
        "raconte-moi une blague",
        # Le nom n'est PAS cherché comme sous-chaîne
        "la lucarne est restée ouverte",
        "arrête tes élucubrations",
        "",
        "   ",
    ],
)
def test_unaddressed_turns_are_rejected(phrase: str) -> None:
    assert not has_wake_word(phrase, CONVERSATION_WAKE_WORDS)


@pytest.mark.parametrize(
    "phrase",
    [
        "je parlais de Lucas à mon frère hier",
        "il faut demander à Lucas ce qu'il en pense",
    ],
)
def test_the_name_mentioned_in_passing_also_passes(phrase: str) -> None:
    """
    ⚠️ CONSÉQUENCE ASSUMÉE de la détection n'importe où (13/08/2026).

    Ces deux phrases prononcent le nom sans s'adresser à Luca's, et elles
    valident pourtant un tour. Le compromis est volontaire : chercher le
    mot uniquement en tête aurait fait rejeter « dis-moi Luca, il est
    quelle heure ? », soit deux formulations orales sur trois. En mains
    libres, manquer une vraie interpellation coûte plus cher que d'en
    accepter une fausse.

    Ce test existe pour que le jour où ce comportement surprend, il soit
    trouvé écrit et daté plutôt que pris pour un bug.
    """
    assert has_wake_word(phrase, CONVERSATION_WAKE_WORDS)


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("Luca, quelle heure est-il ?", "quelle heure est-il ?"),
        ("Luca quelle heure est-il ?", "quelle heure est-il ?"),
        ("Luca's, quelle heure est-il ?", "quelle heure est-il ?"),
        ("Lucas quelle heure est-il ?", "quelle heure est-il ?"),
        ("Lucas ! Raconte-moi une blague", "Raconte-moi une blague"),
        # Au milieu et en fin : le nom part, la question reste entière
        ("dis-moi Luca, il est quelle heure ?", "il est quelle heure ?"),
        ("il est quelle heure Luca ?", "il est quelle heure ?"),
        ("tu m'entends Luca", "tu m'entends"),
        # Les mots d'accompagnement COLLÉS au nom partent avec lui
        ("Hé Luca, raconte-moi une blague", "raconte-moi une blague"),
        ("dis-moi Luca ce que tu penses", "ce que tu penses"),
        ("alors Luca, on y va ?", "on y va ?"),
        # Appelée sans rien dire d'autre : rendu vide, l'appelant doit le voir
        ("Luca", ""),
        ("Lucas", ""),
        ("Luca's ?", ""),
        # Non adressé : le texte revient tel quel, jamais amputé
        ("Thank you. Good night.", "Thank you. Good night."),
    ],
)
def test_the_name_is_removed_but_the_question_is_intact(phrase: str, expected: str) -> None:
    assert strip_wake_word(phrase, CONVERSATION_WAKE_WORDS) == expected


def test_stop_still_works_without_being_addressed() -> None:
    """
    ⚠️ Garde-fou d'ordre, pas de forme : « stop » est le mécanisme d'arrêt
    PRINCIPAL du mode conversation (§5.90). S'il exigeait le mot
    d'adressage, il deviendrait inatteignable exactement quand Cyril en a
    le plus besoin — quand Luca's s'est emballée sur une autre source.
    """
    assert is_stop_command("stop")
    assert is_stop_command("arrête-toi")
    assert not has_wake_word("stop", CONVERSATION_WAKE_WORDS)


def test_fillers_are_only_removed_next_to_the_name() -> None:
    """
    « dis » et « moi » portent du sens ailleurs dans la phrase : ils ne
    partent qu'ACCOLÉS au mot d'adressage, jamais partout.

    Ici « dis-moi » est collé au nom et s'en va avec lui ; le « moi » de
    « ce que moi je devrais » est plus loin, et reste.
    """
    phrase = "Luca, dis-moi ce que moi je devrais en penser"
    assert strip_wake_word(phrase, CONVERSATION_WAKE_WORDS) == (
        "ce que moi je devrais en penser"
    )


def test_a_filler_far_from_the_name_is_untouched() -> None:
    """Le même mot, loin du nom, doit survivre intact."""
    phrase = "il est quelle heure Luca, dis donc"
    # « dis » est collé au nom (juste après la virgule) et part avec lui
    assert strip_wake_word(phrase, CONVERSATION_WAKE_WORDS) == "il est quelle heure donc"
    assert strip_wake_word("Luca, ok pour moi", CONVERSATION_WAKE_WORDS) == "pour moi"


def test_an_unaddressed_turn_is_never_amputated() -> None:
    """Sans interpellation, le texte revient tel quel — jamais raboté."""
    phrase = "Thank you. Good night."
    assert strip_wake_word(phrase, CONVERSATION_WAKE_WORDS) == phrase
