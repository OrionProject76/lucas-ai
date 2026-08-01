# test_server.py — API FastAPI de Luca's
#
# Remplace l'ancien contenu, qui lançait un vrai serveur uvicorn : pytest
# collectait test_server() comme un test et la suite se bloquait
# indéfiniment. D'où son exclusion dans le justfile — exclusion désormais
# inutile.
#
# OrionCore est mocké : aucun appel à Ollama, aucune écriture dans
# memory/orion_memory.db.

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def fake_core(monkeypatch):
    """Remplace OrionCore par un double qui n'ouvre ni base ni LLM."""
    calls: dict[str, object] = {}

    class _FakeCore:
        def ask(self, message: str) -> str:
            calls["asked"] = message
            return f"réponse à « {message} »"

        def history(self):
            return [("user", "bonjour"), ("assistant", "salut")]

        def close(self):
            calls["closed"] = True

    monkeypatch.setattr("api.server.OrionCore", _FakeCore)
    return calls


# ── REST ──────────────────────────────────────────────────────────────

def test_status_confirms_the_server_runs(client) -> None:
    response = client.get("/status")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_system_returns_the_world_model_snapshot(client) -> None:
    response = client.get("/system")
    assert response.status_code == 200
    assert set(response.json()) == {"cpu_percent", "ram_percent", "active_window"}


def test_chat_returns_the_answer(client, fake_core) -> None:
    response = client.post("/chat", json={"message": "quelle heure il est"})
    assert response.status_code == 200
    assert "quelle heure il est" in response.json()["response"]


def test_chat_rejects_an_empty_message(client, fake_core) -> None:
    assert client.post("/chat", json={"message": "   "}).status_code == 400


def test_chat_always_closes_the_core(client, fake_core) -> None:
    """
    Sans fermeture, chaque requête laisserait une connexion SQLite
    ouverte — le serveur finirait par saturer.
    """
    client.post("/chat", json={"message": "test"})
    assert fake_core.get("closed") is True


def test_history_is_returned_as_role_content_pairs(client, fake_core) -> None:
    payload = client.get("/history").json()["history"]
    assert payload == [
        {"role": "user", "content": "bonjour"},
        {"role": "assistant", "content": "salut"},
    ]


# ── WebSocket ─────────────────────────────────────────────────────────

def test_websocket_announces_idle_on_connection(client) -> None:
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json() == {"type": "avatar_state", "state": "idle"}


def test_websocket_chat_cycle(client, fake_core) -> None:
    """Le protocole minimal attendu par Godot : thinking → speaking → idle."""
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()  # idle initial
        ws.send_json({"type": "chat", "message": "bonjour"})

        thinking = ws.receive_json()
        speaking = ws.receive_json()
        idle = ws.receive_json()

    assert thinking["state"] == "thinking"
    assert speaking["state"] == "speaking"
    assert "bonjour" in speaking["text"]
    assert idle["state"] == "idle"


def test_websocket_ignores_an_empty_message(client, fake_core) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "chat", "message": "  "})
        ws.send_json({"type": "chat", "message": "vrai message"})
        assert ws.receive_json()["state"] == "thinking"


# ── Cohérence avec le reste du projet ─────────────────────────────────

def test_world_model_is_not_reimplemented() -> None:
    """
    core/world_model.py affirme dans son en-tête avoir centralisé ce code.
    api/server.py en gardait pourtant une copie : deux implémentations
    qui pouvaient diverger sans que rien ne le signale.
    """
    source = (
        __import__("pathlib").Path("api/server.py").read_text(encoding="utf-8")
    )
    assert "_get_active_window_title" not in source
    assert "get_snapshot" in source


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
