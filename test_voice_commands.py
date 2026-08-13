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
        # La forme PARLÉE de référence, choisie par Cyril le 13/08/2026 :
        # « Luca » seul, plus naturel à dire que « Luca's ».
        "Luca, quelle heure est-il ?",
        "Luca quelle heure est-il ?",
        "luca raconte moi une blague",
        # Ce que Whisper en fait réellement — le français ajoute le « s »
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
    assert has_wake_word(phrase, CONVERSATION_WAKE_WORDS)


@pytest.mark.parametrize(
    "phrase",
    [
        # Le cas réel du 13/08 : la télévision, en anglais
        "Thank you. Good night.",
        "And now, the weather forecast for tomorrow morning.",
        # La télévision en français — la langue ne suffit pas, d'où ce test
        "Et maintenant la météo de demain matin sur toute la région.",
        # Le nom prononcé, mais pas en interpellation
        "je parlais de Lucas à mon frère hier",
        "il faut demander à Lucas ce qu'il en pense",
        "",
        "   ",
    ],
)
def test_unaddressed_turns_are_rejected(phrase: str) -> None:
    assert not has_wake_word(phrase, CONVERSATION_WAKE_WORDS)


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("Luca, quelle heure est-il ?", "quelle heure est-il ?"),
        ("Luca quelle heure est-il ?", "quelle heure est-il ?"),
        ("Luca's, quelle heure est-il ?", "quelle heure est-il ?"),
        ("Lucas quelle heure est-il ?", "quelle heure est-il ?"),
        ("Lucas ! Raconte-moi une blague", "Raconte-moi une blague"),
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
