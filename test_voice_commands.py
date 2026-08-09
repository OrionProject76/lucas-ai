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
