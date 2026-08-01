# test_memory_context.py — mémoire enrichie : événements système dans le prompt
#
# Règle testée : les événements récents enrichissent le contexte local, et
# ne sortent JAMAIS vers le cloud — la table system_events contient des
# extraits de contenu sensible (voir modules/voice_manager.py::_log).
# Voir CLAUDE.md règle 3.

from __future__ import annotations

import pytest

from config import RECENT_EVENTS_IN_PROMPT
from core import orion_core
from core.orion_core import OrionCore
from core.world_model import format_events_for_prompt

# ── format_events_for_prompt() ────────────────────────────────────────

def test_events_are_formatted_most_recent_first() -> None:
    events = [
        ("app_launched", "Visual Studio Code", "2026-08-01 10:00"),
        ("ram_alert", "RAM à 91%", "2026-08-01 09:58"),
    ]
    result = format_events_for_prompt(events)
    assert "app_launched : Visual Studio Code" in result
    assert "ram_alert : RAM à 91%" in result
    assert result.index("app_launched") < result.index("ram_alert")


def test_event_without_details_is_still_listed() -> None:
    result = format_events_for_prompt([("mode_change", "", "2026-08-01 10:00")])
    assert "mode_change" in result
    assert " : " not in result, "pas de séparateur vide quand il n'y a pas de détail"


def test_internal_tts_events_are_excluded() -> None:
    """
    Les événements tts_* décrivent la plomberie d'Orion et contiennent des
    extraits sensibles. Les réinjecter polluerait toutes les conversations
    suivantes.
    """
    events = [
        ("tts_skipped_sensitive", "Modèle absent | Mon salaire est de 3200 euros", "2026-08-01"),
        ("app_launched", "Chrome", "2026-08-01"),
    ]
    result = format_events_for_prompt(events)
    assert "3200 euros" not in result
    assert "tts_skipped_sensitive" not in result
    assert "Chrome" in result


def test_no_relevant_event_returns_empty_string() -> None:
    """Chaîne vide = l'appelant n'ajoute aucun message, pas un bloc vide."""
    assert format_events_for_prompt([]) == ""
    assert format_events_for_prompt([("tts_cloud_on_sensitive", "x", "2026-08-01")]) == ""


# ── Injection dans _build_messages() ──────────────────────────────────

class _FakeMemory:
    def __init__(self, events: list[tuple[str, str, str]]) -> None:
        self._events = events
        self.requested_limit: int | None = None

    def load_history(self) -> list[tuple[str, str]]:
        return [("user", "bonjour")]

    def load_recent_events(self, limit: int = 5) -> list[tuple[str, str, str]]:
        self.requested_limit = limit
        return self._events[:limit]


@pytest.fixture
def core_with_events(monkeypatch) -> tuple[OrionCore, _FakeMemory]:
    monkeypatch.setattr(orion_core, "get_snapshot", dict)
    monkeypatch.setattr(orion_core, "format_for_prompt", lambda snapshot: "[système]")
    monkeypatch.setattr(orion_core, "RAGManager", lambda: None)

    memory = _FakeMemory([
        ("app_launched", "Chrome", "2026-08-01 10:00"),
        ("ram_alert", "RAM à 91%", "2026-08-01 09:58"),
    ])
    core = OrionCore.__new__(OrionCore)
    core.memory = memory
    return core, memory


def test_local_prompt_contains_events(core_with_events) -> None:
    core, _memory = core_with_events
    messages = core._build_messages("comment ça va ?", "local")
    assert any("app_launched" in m["content"] for m in messages)


def test_cloud_prompt_never_contains_events(core_with_events) -> None:
    """Le point de sécurité : rien de la table system_events ne sort."""
    core, _memory = core_with_events
    messages = core._build_messages("compare ces options", "cloud")
    assert not any("app_launched" in m["content"] for m in messages)
    assert not any("Événements système" in m["content"] for m in messages)


def test_event_limit_comes_from_config(core_with_events) -> None:
    core, memory = core_with_events
    core._build_messages("bonjour", "local")
    assert memory.requested_limit == RECENT_EVENTS_IN_PROMPT


def test_no_empty_system_message_when_no_events(monkeypatch) -> None:
    """Aucun événement pertinent : pas de message système vide dans le prompt."""
    monkeypatch.setattr(orion_core, "get_snapshot", dict)
    monkeypatch.setattr(orion_core, "format_for_prompt", lambda snapshot: "[système]")

    core = OrionCore.__new__(OrionCore)
    core.memory = _FakeMemory([])
    messages = core._build_messages("bonjour", "local")

    assert all(m["content"].strip() for m in messages), "aucun message vide"
    assert len([m for m in messages if m["role"] == "system"]) == 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
