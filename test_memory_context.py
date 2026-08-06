# test_memory_context.py — mémoire enrichie : événements système dans le prompt
#
# Règle testée : les événements récents enrichissent le contexte local, et
# ne sortent JAMAIS vers le cloud — la table system_events contient des
# extraits de contenu sensible (voir modules/voice_manager.py::_log).
# Voir CLAUDE.md règle 3.

from __future__ import annotations

import pytest

from config import RECENT_EVENTS_IN_PROMPT
from core import lucas_core
from core.lucas_core import LucasCore
from core.world_model import format_events_for_prompt
from test_memory_double import MemoryDouble

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
    Les événements tts_* décrivent la plomberie de Luca's et contiennent des
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


# ── format_for_prompt() : le titre de fenêtre ─────────────────────────

def test_window_title_is_omitted_when_asked() -> None:
    """
    Un titre de fenêtre est une donnée personnelle en soi : il révèle sur
    quoi Cyril travaille, même quand la question posée est anodine.
    """
    from core.world_model import format_for_prompt

    snapshot = {
        "cpu_percent": 12.0,
        "ram_percent": 44.0,
        "active_window": "releve_bancaire_2026.pdf - Acrobat",
        "local_time": "samedi 02/08/2026 21:00",
    }

    with_window = format_for_prompt(snapshot)
    without_window = format_for_prompt(snapshot, include_window=False)

    assert "releve_bancaire" in with_window
    assert "releve_bancaire" not in without_window
    # CPU et RAM ne disent rien de Cyril : ils restent dans les deux cas.
    assert "CPU 12.0%" in without_window
    assert "RAM 44.0%" in without_window


# ── Injection dans _build_messages() ──────────────────────────────────

class _FakeMemory(MemoryDouble):
    def __init__(self, events: list[tuple[str, str, str]]) -> None:
        super().__init__()
        self._events = events
        self.requested_limit: int | None = None

    def load_history(self) -> list[tuple[str, str]]:
        return [("user", "bonjour")]

    def load_history_with_metadata(self) -> list[dict]:
        return [
            {"role": r, "message": m, "confidence": 1.0, "importance": 0.5, "expiration": None}
            for r, m in self.load_history()
        ]

    def load_recent_events(self, limit: int = 5) -> list[tuple[str, str, str]]:
        self.requested_limit = limit
        return self._events[:limit]

    def load_recent_events_with_metadata(self, limit: int = 5) -> list[dict]:
        return [
            {
                "event_type": event_type, "details": details, "date": created_at,
                "confidence": 1.0, "importance": 0.5, "expiration": None,
            }
            for event_type, details, created_at in self.load_recent_events(limit)
        ]


@pytest.fixture
def core_with_events(monkeypatch) -> tuple[LucasCore, _FakeMemory]:
    monkeypatch.setattr(lucas_core, "get_snapshot", dict)
    monkeypatch.setattr(
        lucas_core, "format_for_prompt",
        lambda snapshot, include_window=True: "[système]",
    )
    monkeypatch.setattr(lucas_core, "RAGManager", lambda: None)

    memory = _FakeMemory([
        ("app_launched", "Chrome", "2026-08-01 10:00"),
        ("ram_alert", "RAM à 91%", "2026-08-01 09:58"),
    ])
    core = LucasCore.__new__(LucasCore)
    core.memory = memory  # type: ignore[assignment]  # double assume, voir test_memory_double.py
    return core, memory


def test_local_prompt_contains_events(core_with_events) -> None:
    core, _memory = core_with_events
    messages = core._build_messages("comment ça va ?", "local")
    assert any("app_launched" in m["content"] for m in messages)


def test_cloud_prompt_omits_window_title(monkeypatch) -> None:
    """
    Intégration, avec le vrai format_for_prompt : le titre de fenêtre ne
    doit apparaître que dans le prompt local.
    """
    monkeypatch.setattr(lucas_core, "get_snapshot", lambda: {
        "cpu_percent": 10.0,
        "ram_percent": 30.0,
        "active_window": "budget_2026.xlsx - Excel",
        "local_time": "samedi 02/08/2026 21:00",
    })

    core = LucasCore.__new__(LucasCore)
    core.memory = _FakeMemory([])  # type: ignore[assignment]  # double assume, voir test_memory_double.py

    local = " ".join(m["content"] for m in core._build_messages("bonjour", "local"))
    cloud = " ".join(m["content"] for m in core._build_messages("bonjour", "cloud"))

    assert "budget_2026.xlsx" in local
    assert "budget_2026.xlsx" not in cloud, "le titre de fenêtre ne doit jamais sortir"
    assert "CPU 10.0%" in cloud, "CPU et RAM restent joints, ils ne disent rien de Cyril"


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
    monkeypatch.setattr(lucas_core, "get_snapshot", dict)
    monkeypatch.setattr(
        lucas_core, "format_for_prompt",
        lambda snapshot, include_window=True: "[système]",
    )

    core = LucasCore.__new__(LucasCore)
    core.memory = _FakeMemory([])  # type: ignore[assignment]  # double assume, voir test_memory_double.py
    messages = core._build_messages("bonjour", "local")

    assert all(m["content"].strip() for m in messages), "aucun message vide"
    # Le nombre exact de blocs système n'est PAS la propriété testée ici —
    # il change dès qu'une capacité en ajoute un (le bloc [Contexte] de
    # présence l'a fait passer de 2 à 3 le 05/08/2026). Ce qui compte, et
    # que ce test protège vraiment : aucun bloc VIDE, et aucun bloc
    # d'événements quand il n'y a pas d'événement.
    systeme = [m["content"] for m in messages if m["role"] == "system"]
    assert not any("Événements système récents" in c for c in systeme)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
