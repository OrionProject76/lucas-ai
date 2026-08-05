# test_ollama_reply.py — extraction de la réponse utile d'un message Ollama
#
# Module écrit le 05/08/2026 pour la bascule sur gpt-oss:20b, qui rend
# DEUX champs (`content` et `thinking`) au lieu d'un. Sa logique est plus
# subtile qu'elle n'en a l'air — récupération d'une conclusion, plafond
# de longueur, refus de concaténer — et elle décide de ce que Cyril voit
# à l'écran. Elle mérite donc mieux qu'une relecture.

from __future__ import annotations

import pytest

from core.ollama_reply import extract_reply


# ── Cas normal : `content` prime toujours ─────────────────────────────


def test_content_is_returned_when_present() -> None:
    assert extract_reply({"content": "Il est 12 h 30."}) == "Il est 12 h 30."


def test_content_wins_over_thinking() -> None:
    """
    Le raisonnement n'est JAMAIS préféré à la réponse. C'est un brouillon
    en anglais, avec des hésitations et des pistes abandonnées.
    """
    message = {"content": "qu'il résolût", "thinking": "We need to conjugate..."}
    assert extract_reply(message) == "qu'il résolût"


def test_the_two_fields_are_never_concatenated() -> None:
    """
    Afficher les deux ferait passer le brouillon pour une partie de la
    réponse — le contraire de ce que ce module existe pour éviter.
    """
    resultat = extract_reply({"content": "La réponse.", "thinking": "Le brouillon."})
    assert "brouillon" not in resultat


def test_content_is_stripped() -> None:
    assert extract_reply({"content": "  réponse  "}) == "réponse"


# ── Récupération dans `thinking` quand `content` est vide ─────────────
#
# Mesuré sur cette machine : 2 réponses vides sur 16 avec gpt-oss:20b.


def test_an_explicit_conclusion_marker_is_used() -> None:
    """
    Le meilleur repêchage possible : c'est le modèle lui-même qui désigne
    sa réponse.
    """
    message = {"content": "", "thinking": "Let me think about this.\nFinal answer: 42"}
    assert extract_reply(message) == "42"


def test_the_last_marker_wins() -> None:
    """
    Un raisonnement revient parfois sur sa conclusion. C'est la dernière
    qui vaut, pas la première.
    """
    message = {
        "content": "",
        "thinking": "Answer: 41\nWait, that's wrong.\nFinal answer: 42",
    }
    assert extract_reply(message) == "42"


def test_a_french_marker_is_recognized() -> None:
    message = {"content": "", "thinking": "On analyse.\nRéponse finale : ECRAN"}
    assert extract_reply(message) == "ECRAN"


def test_the_last_paragraph_is_used_without_a_marker() -> None:
    """
    Sans marqueur annoncé, ces modèles posent leur conclusion en dernier
    paragraphe. C'est le repêchage de second rang.
    """
    message = {"content": "", "thinking": "D'abord ceci.\n\nDonc la réponse est ECRAN."}
    assert extract_reply(message) == "Donc la réponse est ECRAN."


# ── Le refus : mieux vaut rien qu'un brouillon ────────────────────────


def test_a_long_reasoning_without_conclusion_returns_nothing() -> None:
    """
    Cas réel observé : 11 400 caractères de raisonnement, zéro réponse.
    Les afficher ferait passer un monologue anglais pour une réponse de
    Luca. Rendre vide oblige l'appelant à le DIRE (même doctrine §5.39).
    """
    message = {"content": "", "thinking": "x" * 11_000}
    assert extract_reply(message) == ""


def test_a_marker_followed_by_a_huge_block_is_refused() -> None:
    """
    Un marqueur ne suffit pas : ce qui suit doit rester d'une taille
    plausible pour une réponse. Sinon c'est encore du brouillon.
    """
    message = {"content": "", "thinking": "Final answer: " + "y" * 5_000}
    assert extract_reply(message) == ""


def test_an_empty_message_returns_an_empty_string() -> None:
    assert extract_reply({"content": "", "thinking": ""}) == ""


def test_a_missing_field_does_not_raise() -> None:
    assert extract_reply({}) == ""
    assert extract_reply({"role": "assistant"}) == ""


@pytest.mark.parametrize("valeur", [None, "pas un dict", 42, []])
def test_a_malformed_message_returns_an_empty_string(valeur) -> None:
    """
    Ce module est appelé sur du JSON venu du réseau. Il ne doit jamais
    lever — l'appelant a déjà ses propres branches d'erreur.
    """
    assert extract_reply(valeur) == ""


def test_none_values_are_tolerated() -> None:
    """Ollama peut rendre `null` plutôt qu'omettre le champ."""
    assert extract_reply({"content": None, "thinking": None}) == ""
    assert extract_reply({"content": None, "thinking": "Final answer: ok"}) == "ok"


# ── Le cas qui a motivé le module, de bout en bout ────────────────────


def test_the_real_gpt_oss_shape_is_handled() -> None:
    """
    Forme réellement observée le 05/08/2026 en interrogeant gpt-oss:20b :
    `thinking` rempli, `content` court mais présent. Le contenu doit
    passer tel quel, sans que le raisonnement ne l'approche.
    """
    message = {
        "role": "assistant",
        "thinking": 'User: "Conjugue le verbe résoudre..." We need to respond '
                    "in French, direct, no formalities. Use tu.",
        "content": "qu'il résolût",
    }
    assert extract_reply(message) == "qu'il résolût"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
