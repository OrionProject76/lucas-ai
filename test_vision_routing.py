# test_vision_routing.py — Luca's regarde l'écran, et seulement quand il faut
#
# Deux propriétés testées :
#   1. La capture ne se déclenche que sur une demande explicite — un VLM
#      coûte plusieurs secondes, le lancer à chaque message est exclu.
#   2. Une question sur l'écran est forcée en LOCAL. L'image ne part
#      jamais, mais sa description en dirait autant.
#
# Aucune capture réelle, aucun appel à Ollama : VisionManager est mocké.

from __future__ import annotations

import pytest

from core import orion_core
from core.orion_core import OrionCore
from core.router import route, should_use_vision


# ── Déclencheur ───────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "question",
    [
        "qu'est-ce que tu vois à l'écran ?",
        "regarde mon écran",
        "c'est quoi cette erreur ?",
        "aide-moi avec cette fenêtre",
        "que vois-tu ?",
        "fais une capture d'écran",
    ],
)
def test_explicit_requests_trigger_vision(question: str) -> None:
    assert should_use_vision(question)


@pytest.mark.parametrize(
    "question",
    [
        "quelle heure il est",
        "raconte-moi une blague",
        "regarde si tu peux m'aider",
        "explique-moi les tableaux Python",
        "quel temps fait-il demain",
    ],
)
def test_ordinary_questions_do_not_trigger_vision(question: str) -> None:
    """
    Une capture + analyse VLM coûte plusieurs secondes. « regarde si tu
    peux m'aider » ne doit surtout pas la déclencher.
    """
    assert not should_use_vision(question)


# ── Routage ───────────────────────────────────────────────────────────

def test_a_screen_question_stays_local() -> None:
    """
    L'image reste sur la machine, mais « une fenêtre affichant un solde
    de 3200 € » est tout aussi révélateur. La question doit donc être
    traitée en local.
    """
    assert route("regarde mon écran et analyse cette projection") == "local"


def test_vision_beats_a_cloud_keyword() -> None:
    """« analyse » enverrait au cloud ; la vision doit l'emporter."""
    assert route("analyse ce qui est à l'écran") == "local"


# ── Injection dans le prompt ──────────────────────────────────────────

class _FakeMemory:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def load_history(self):
        return []

    def load_recent_events(self, limit=5):
        return []

    def save_event(self, event_type, details=""):
        self.events.append((event_type, details))


@pytest.fixture
def core(monkeypatch):
    monkeypatch.setattr(orion_core, "get_snapshot", dict)
    monkeypatch.setattr(
        orion_core, "format_for_prompt",
        lambda snapshot, include_window=True: "[système]",
    )
    instance = OrionCore.__new__(OrionCore)
    instance.memory = _FakeMemory()
    return instance


def _fake_vision(monkeypatch, description: str):
    class _FakeVisionManager:
        def __init__(self, model=None):
            self.model = model

        def see_and_describe(self):
            return description

    monkeypatch.setattr(
        "modules.vision_manager.VisionManager", _FakeVisionManager
    )


def test_screen_description_reaches_the_prompt(core, monkeypatch) -> None:
    _fake_vision(monkeypatch, "un éditeur de code affichant du Python")
    messages = core._build_messages("qu'est-ce que tu vois à l'écran ?", "local")
    assert any("éditeur de code" in m["content"] for m in messages)


def test_no_capture_without_an_explicit_request(core, monkeypatch) -> None:
    """Le VLM ne doit pas être sollicité pour une question ordinaire."""
    def must_not_be_called(model=None):
        raise AssertionError("aucune capture ne doit être déclenchée")

    monkeypatch.setattr("modules.vision_manager.VisionManager", must_not_be_called)
    core._build_messages("quelle heure il est", "local")


def test_no_capture_on_a_cloud_request(core, monkeypatch) -> None:
    """Garde redondante : même si route() se trompait, rien ne part."""
    def must_not_be_called(model=None):
        raise AssertionError("pas de vision sur un chemin cloud")

    monkeypatch.setattr("modules.vision_manager.VisionManager", must_not_be_called)
    messages = core._build_messages("regarde mon écran", "cloud")
    assert not any("Écran de Cyril" in m["content"] for m in messages)


def test_vision_can_be_disabled(core, monkeypatch) -> None:
    monkeypatch.setattr(orion_core, "VISION_ENABLED", False)

    def must_not_be_called(model=None):
        raise AssertionError("VISION_ENABLED=False doit tout couper")

    monkeypatch.setattr("modules.vision_manager.VisionManager", must_not_be_called)
    core._build_messages("regarde mon écran", "local")


def test_vision_use_is_logged(core, monkeypatch) -> None:
    _fake_vision(monkeypatch, "un bureau")
    core._build_messages("regarde mon écran", "local")
    assert "vision_used" in [t for t, _ in core.memory.events]


# ── Dégradation ───────────────────────────────────────────────────────

def test_vlm_failure_does_not_block_the_answer(core, monkeypatch) -> None:
    """
    Une vision indisponible doit dégrader la réponse, pas empêcher
    Luca's de répondre.
    """
    _fake_vision(monkeypatch, "Erreur analyse (modèle llava peut-être non installé)")
    messages = core._build_messages("regarde mon écran", "local")

    assert not any("Écran de Cyril" in m["content"] for m in messages)
    assert messages, "le prompt doit rester exploitable"
    assert "vision_failed" in [t for t, _ in core.memory.events]


def test_vlm_exception_is_caught(core, monkeypatch) -> None:
    class _Broken:
        def __init__(self, model=None):
            raise ConnectionError("Ollama injoignable")

    monkeypatch.setattr("modules.vision_manager.VisionManager", _Broken)
    messages = core._build_messages("regarde mon écran", "local")

    assert messages
    assert "vision_failed" in [t for t, _ in core.memory.events]


def test_empty_description_is_not_injected(core, monkeypatch) -> None:
    _fake_vision(monkeypatch, "")
    messages = core._build_messages("regarde mon écran", "local")
    assert all(m["content"].strip() for m in messages)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
