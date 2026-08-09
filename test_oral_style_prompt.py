# test_oral_style_prompt.py — instruction de style oral ajoutée au prompt
# quand speak=True (ROADMAP.md §5.86).
#
# Cyril signale que la voix de Luca sonne trop littéraire. `speak` n'était
# threadé nulle part jusqu'à LucasCore.ask()/_build_messages() — utilisé
# uniquement APRÈS coup, côté serveur, pour décider de synthétiser le
# texte déjà généré (api/server.py). Ce fichier couvre le nouveau
# threading : ORAL_STYLE_INSTRUCTION apparaît dans le prompt seulement
# quand speak=True, jamais sinon, et est répétée au ré-ancrage comme la
# règle de tutoiement (même raisonnement, même fichier).

from __future__ import annotations

from config import ORAL_STYLE_INSTRUCTION
from core.lucas_core import LucasCore
from test_memory_double import MemoryDouble


def _core():
    instance = LucasCore.__new__(LucasCore)
    instance.memory = MemoryDouble()  # type: ignore[assignment]  # double assumé, voir test_memory_double.py
    return instance


def test_speak_true_adds_the_oral_style_instruction() -> None:
    messages = _core()._build_messages("bonjour", "local", speak=True)
    assert any(m["content"] == ORAL_STYLE_INSTRUCTION for m in messages)


def test_speak_false_never_adds_it() -> None:
    messages = _core()._build_messages("bonjour", "local", speak=False)
    assert not any(m["content"] == ORAL_STYLE_INSTRUCTION for m in messages)


def test_speak_defaults_to_false() -> None:
    """Le texte affiché (chat sans voix) ne doit jamais être concerné par défaut."""
    messages = _core()._build_messages("bonjour", "local")
    assert not any(m["content"] == ORAL_STYLE_INSTRUCTION for m in messages)


def test_it_applies_on_cloud_too() -> None:
    """
    C'est une consigne de STYLE, pas de sensibilité — contrairement au
    contexte système/RAG/événements, elle n'a aucune raison d'être
    retirée quand la question part vers le cloud.
    """
    messages = _core()._build_messages("bonjour", "cloud", speak=True)
    assert any(m["content"] == ORAL_STYLE_INSTRUCTION for m in messages)


def test_it_is_repeated_at_the_reanchor_point_with_history() -> None:
    """
    Même raisonnement que le ré-ancrage du tutoiement (SYSTEM_PROMPT
    répété juste avant la question) : une règle de style qui lutte
    contre le fil de la conversation a besoin d'être répétée près de la
    question, pas seulement en tête de prompt.
    """
    core = _core()
    core.memory.save_message("user", "salut")
    core.memory.save_message("assistant", "salut, ça va ?")
    messages = core._build_messages("et toi ?", "local", speak=True)
    occurrences = sum(1 for m in messages if m["content"] == ORAL_STYLE_INSTRUCTION)
    assert occurrences >= 2
