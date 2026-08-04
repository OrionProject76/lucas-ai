# test_lucas_core.py — LucasCore.ask() et les petites méthodes qui
# l'entourent (prepare, save_response, history, log_event, close, _emit).
#
# _build_messages() est déjà couvert en détail ailleurs (test_router.py,
# test_vision_routing.py, test_memory_context.py, test_history_budget.py)
# — ce fichier teste l'ORCHESTRATION autour d'elle : sauvegarde du
# message avant/après, routage local/cloud, timing, callback d'activité.
# Trouvé via mesure de couverture réelle (Priorité 3, 04/08/2026) :
# ask() n'était exercé que par les tests d'intégration (marqueur
# "integration", réclame un vrai Ollama, exclus du run par défaut).

from __future__ import annotations

import pytest

from core import lucas_core
from core.lucas_core import LucasCore


class _FakeMemory:
    def __init__(self) -> None:
        self.saved: list[tuple[str, str]] = []
        self.events: list[tuple[str, str]] = []

    def save_message(self, role: str, content: str) -> None:
        self.saved.append((role, content))

    def load_history(self):
        return list(self.saved)

    def load_recent_events(self, limit=5):
        return []

    def save_event(self, event_type: str, details: str = "") -> None:
        self.events.append((event_type, details))

    def close(self) -> None:
        self.saved.append(("__closed__", ""))


@pytest.fixture
def core(monkeypatch):
    monkeypatch.setattr(lucas_core, "route", lambda text, context="": "local")
    monkeypatch.setattr(
        lucas_core.LucasCore, "_build_messages",
        lambda self, *a, **k: [{"role": "user", "content": "peu importe"}],
    )
    monkeypatch.setattr(lucas_core, "ask_local", lambda messages: "réponse locale")
    monkeypatch.setattr(lucas_core, "ask_cloud", lambda messages: "réponse cloud")

    instance = LucasCore.__new__(LucasCore)
    instance.memory = _FakeMemory()
    return instance


def test_ask_saves_the_user_message_before_building_the_prompt(core) -> None:
    """
    Sans cet ordre, _build_messages() ne verrait pas la question dans
    l'historique (voir le commentaire "ORDRE CRITIQUE" de _build_messages).
    """
    core.ask("bonjour")
    assert core.memory.saved[0] == ("user", "bonjour")


def test_ask_saves_the_answer_after_generating_it(core) -> None:
    answer = core.ask("bonjour")
    assert core.memory.saved[-1] == ("assistant", "réponse locale")
    assert answer == "réponse locale"


def test_ask_routes_to_ask_local_when_destination_is_local(monkeypatch, core) -> None:
    monkeypatch.setattr(lucas_core, "route", lambda text, context="": "local")
    assert core.ask("bonjour") == "réponse locale"


def test_ask_routes_to_ask_cloud_when_destination_is_cloud(monkeypatch, core) -> None:
    monkeypatch.setattr(lucas_core, "route", lambda text, context="": "cloud")
    assert core.ask("compare ces stratégies") == "réponse cloud"


def test_ask_emits_routed_then_answered(core) -> None:
    events: list[tuple[str, str]] = []
    core.ask("bonjour", on_activity=lambda kind, text: events.append((kind, text)))

    kinds = [kind for kind, _text in events]
    assert kinds == ["routed", "answered"]
    assert "LOCAL" in events[0][1]
    assert "s)" in events[1][1], "le temps de réponse doit être annoncé"


def test_ask_activity_mentions_cloud_when_routed_there(monkeypatch, core) -> None:
    monkeypatch.setattr(lucas_core, "route", lambda text, context="": "cloud")
    events: list[tuple[str, str]] = []
    core.ask("compare", on_activity=lambda kind, text: events.append((kind, text)))

    assert "CLOUD" in events[0][1]


def test_ask_without_on_activity_does_not_crash(core) -> None:
    assert core.ask("bonjour") == "réponse locale"


def test_prepare_saves_the_message_and_always_stays_local(monkeypatch, core) -> None:
    captured = {}
    monkeypatch.setattr(
        lucas_core.LucasCore, "_build_messages",
        lambda self, user_message, destination="local", **k: captured.update(
            destination=destination
        )
        or [{"role": "user", "content": user_message}],
    )

    core.prepare("bonjour")

    assert core.memory.saved == [("user", "bonjour")]
    assert captured["destination"] == "local"


def test_save_response_appends_an_assistant_message(core) -> None:
    core.save_response("voilà")
    assert core.memory.saved == [("assistant", "voilà")]


def test_history_returns_the_raw_memory_history(core) -> None:
    core.memory.saved = [("user", "a"), ("assistant", "b")]
    assert core.history() == [("user", "a"), ("assistant", "b")]


def test_log_event_delegates_to_memory(core) -> None:
    core.log_event("test_event", "détail")
    assert core.memory.events == [("test_event", "détail")]


def test_close_closes_the_memory(core) -> None:
    core.close()
    assert ("__closed__", "") in core.memory.saved


# ── _emit() : jamais d'exception, callback optionnel ───────────────────

def test_emit_does_nothing_without_a_callback() -> None:
    lucas_core._emit(None, "kind", "texte")  # ne doit pas lever


def test_emit_calls_the_callback_with_both_arguments() -> None:
    received = []
    lucas_core._emit(lambda kind, text: received.append((kind, text)), "screen_read", "ok")
    assert received == [("screen_read", "ok")]


def test_emit_swallows_a_callback_that_raises() -> None:
    """
    ⚠️ Trouvé documenté mais jamais testé : une console de flux dont le
    WebSocket vient de se fermer ne doit jamais faire échouer la réponse
    à Cyril.
    """
    def _broken(kind, text):
        raise RuntimeError("WebSocket fermé")

    lucas_core._emit(_broken, "kind", "texte")  # ne doit pas lever


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
