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
    assert set(response.json()) == {
        "cpu_percent", "ram_percent", "gpu_percent", "active_window",
    }


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

def _next_of_type(ws, message_type: str, limit: int = 12) -> dict:
    """
    Lit jusqu'au prochain message du type demandé.

    Le canal transporte aussi la charge machine, poussée en continu pour
    le HUD Godot. Un client ne peut donc pas supposer un ordre strict :
    il dispatche par type, comme le fait websocket_client.gd. Les tests
    doivent en faire autant, sinon ils testent une hypothèse que le vrai
    client ne partage pas.
    """
    for _ in range(limit):
        message = ws.receive_json()
        if message.get("type") == message_type:
            return message
    raise AssertionError(f"aucun message « {message_type} » reçu")


def test_websocket_announces_idle_on_connection(client) -> None:
    with client.websocket_connect("/ws") as ws:
        first = _next_of_type(ws, "avatar_state")
        assert first["state"] == "idle"


def test_websocket_pushes_system_load(client) -> None:
    """Le HUD Godot attend cpu/ram/gpu sans avoir à les demander."""
    with client.websocket_connect("/ws") as ws:
        message = _next_of_type(ws, "system")

    assert set(message) == {"type", "cpu", "ram", "gpu"}


def test_websocket_chat_cycle(client, fake_core) -> None:
    """Le cycle attendu par Godot : thinking → speaking → idle."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "bonjour"})

        states = []
        answer = None
        for _ in range(15):
            message = ws.receive_json()
            if message.get("type") == "avatar_state":
                states.append(message["state"])
                if message["state"] == "speaking":
                    answer = message.get("text", "")
            if states[-3:] == ["thinking", "speaking", "idle"]:
                break

    assert states[-3:] == ["thinking", "speaking", "idle"]
    assert "bonjour" in answer


def test_websocket_also_emits_a_chat_message(client, fake_core) -> None:
    """
    Deux messages pour une réponse : l'état pilote l'animation du visage,
    le message de chat alimente la bulle du HUD.
    """
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "bonjour"})
        message = _next_of_type(ws, "chat")

    assert message["from_orion"] is True
    assert "bonjour" in message["text"]


def test_websocket_accepts_the_godot_text_field(client, fake_core) -> None:
    """Le client Godot envoie « text » là où l'API attendait « message »."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "text": "depuis godot"})
        message = _next_of_type(ws, "chat")

    assert "depuis godot" in message["text"]


def test_websocket_answers_the_godot_handshake(client) -> None:
    """websocket_client.gd envoie « hello » dès la connexion."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "hello", "client": "orion3d_godot"})
        message = _next_of_type(ws, "chat")

    assert "connectée" in message["text"]


def test_websocket_ignores_an_empty_message(client, fake_core) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "  "})
        ws.send_json({"type": "chat", "message": "vrai message"})
        assert _next_of_type(ws, "avatar_state", limit=20)["state"] in {"idle", "thinking"}


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
