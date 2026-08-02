# test_server.py — API FastAPI de Luca's
#
# Remplace l'ancien contenu, qui lançait un vrai serveur uvicorn : pytest
# collectait test_server() comme un test et la suite se bloquait
# indéfiniment. D'où son exclusion dans le justfile — exclusion désormais
# inutile.
#
# LucasCore est mocké : aucun appel à Ollama, aucune écriture dans
# memory/lucas_memory.db.

from __future__ import annotations

import base64
import os

import pytest
from fastapi.testclient import TestClient

from api.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def fake_core(monkeypatch):
    """Remplace LucasCore par un double qui n'ouvre ni base ni LLM."""
    calls: dict[str, object] = {}

    class _FakeCore:
        def ask(self, message: str, image_path: str | None = None) -> str:
            calls["asked"] = message
            calls["asked_image_path"] = image_path
            # Capturé PENDANT l'appel : le fichier temporaire est supprimé
            # juste après, dans le finally de websocket_endpoint.
            calls["image_existed_during_call"] = (
                image_path is not None and os.path.exists(image_path)
            )
            return f"réponse à « {message} »"

        def history(self):
            return [("user", "bonjour"), ("assistant", "salut")]

        def close(self):
            calls["closed"] = True

    monkeypatch.setattr("api.server.LucasCore", _FakeCore)
    return calls


@pytest.fixture
def fake_stt(monkeypatch):
    """
    Remplace le moteur STT partagé par un double — aucun modèle Whisper
    chargé, aucun fichier temporaire écrit.
    """
    from modules.stt_engine import STTUnavailable, TranscriptResult

    calls: dict[str, object] = {}

    class _FakeSTT:
        def __init__(self, texte="audio transcrit", boom=None):
            self.texte = texte
            self.boom = boom

        def transcribe_base64(self, audio_base64, suffix=".wav"):
            calls["audio_base64"] = audio_base64
            if self.boom:
                raise self.boom
            return TranscriptResult(
                text=self.texte, language="fr", confidence=0.9, duration_seconds=1.5,
            )

    double = _FakeSTT()
    monkeypatch.setattr("api.server._stt_engine", double)
    calls["_double"] = double  # pour permuter texte/boom depuis un test
    calls["_STTUnavailable"] = STTUnavailable
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

    assert message["from_lucas"] is True
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
        ws.send_json({"type": "hello", "client": "lucas3d_godot"})
        message = _next_of_type(ws, "chat")

    assert "connectée" in message["text"]


def test_websocket_ignores_an_empty_message(client, fake_core) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "  "})
        ws.send_json({"type": "chat", "message": "vrai message"})
        assert _next_of_type(ws, "avatar_state", limit=20)["state"] in {"idle", "thinking"}


# ── WebSocket : audio (pont mobile, Phase 4) ───────────────────────────
#
# Premier appelant réel de modules/stt_engine.py — jusqu'ici écrit et
# testé, mais rien ne l'alimentait (voir son en-tête). Ces tests
# vérifient le CHEMIN serveur, pas la qualité de la transcription : le
# moteur STT est entièrement doublé.

def test_websocket_audio_is_transcribed_and_answered(client, fake_core, fake_stt) -> None:
    """Le cycle attendu : listening → thinking → speaking → idle."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "audio", "audio_base64": "ZmF1eCBhdWRpbw=="})

        states = []
        answer = None
        for _ in range(20):
            message = ws.receive_json()
            if message.get("type") == "avatar_state":
                states.append(message["state"])
                if message["state"] == "speaking":
                    answer = message.get("text", "")
            if states[-4:] == ["listening", "thinking", "speaking", "idle"]:
                break

    assert states[-4:] == ["listening", "thinking", "speaking", "idle"]
    # fake_core renvoie "réponse à « <message demandé> »" — le message
    # demandé doit être le texte transcrit, pas l'audio brut.
    assert "audio transcrit" in answer


def test_websocket_audio_reaches_the_stt_engine(client, fake_core, fake_stt) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "audio", "audio_base64": "ZmF1eCBhdWRpbw=="})
        _next_of_type(ws, "chat")

    assert fake_stt["audio_base64"] == "ZmF1eCBhdWRpbw=="


def test_websocket_audio_transcript_is_asked_to_lucas(client, fake_core, fake_stt) -> None:
    """Le transcrit doit suivre EXACTEMENT le même chemin qu'un message tapé."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "audio", "audio_base64": "ZmF1eCBhdWRpbw=="})
        _next_of_type(ws, "chat")

    assert fake_core.get("asked") == "audio transcrit"


def test_websocket_ignores_audio_without_the_field(client, fake_core, fake_stt) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "audio"})
        ws.send_json({"type": "chat", "message": "vrai message"})
        message = _next_of_type(ws, "chat", limit=20)

    assert "vrai message" in message["text"]
    assert "audio_base64" not in fake_stt


def test_websocket_stt_unavailable_reports_an_error_not_a_crash(client, fake_core, fake_stt) -> None:
    """
    Un doute sur l'audio ne doit jamais planter la connexion — mais
    contrairement au chemin vision, Cyril doit savoir qu'on ne l'a pas
    entendu : un silence serait plus trompeur qu'un message d'erreur.
    """
    fake_stt["_double"].boom = fake_stt["_STTUnavailable"]("aucun backend Whisper")

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "audio", "audio_base64": "ZmF1eCBhdWRpbw=="})
        error = _next_of_type(ws, "error")
        idle = _next_of_type(ws, "avatar_state")

    assert "Whisper" in error["detail"]
    assert idle["state"] == "idle"


def test_websocket_silence_returns_to_idle_without_asking_lucas(client, fake_core, fake_stt) -> None:
    """
    Un extrait sans parole (texte transcrit vide) ne doit pas devenir une
    question vide envoyée à LucasCore.ask().
    """
    fake_stt["_double"].texte = ""

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "audio", "audio_base64": "ZmF1eCBhdWRpbw=="})
        ws.send_json({"type": "chat", "message": "toujours vivant"})
        message = _next_of_type(ws, "chat", limit=20)

    assert "toujours vivant" in message["text"]
    assert "asked" not in fake_core or fake_core["asked"] != ""


# ── Jeton API (prérequis pont mobile) ──────────────────────────────────
#
# API_TOKEN est vide par défaut (config.py) : ces tests forcent une
# valeur pour vérifier le mécanisme, mais le comportement PAR DÉFAUT —
# testé partout ailleurs dans ce fichier, sans jeton — ne doit jamais
# changer tant que Cyril n'a rien renseigné dans .env.

def test_status_never_requires_a_token(client, monkeypatch) -> None:
    """Ping de santé — rien de sensible, ouvert même quand un jeton existe."""
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    assert client.get("/status").status_code == 200


def test_chat_without_token_is_rejected_once_one_is_set(client, fake_core, monkeypatch) -> None:
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    response = client.post("/chat", json={"message": "test"})
    assert response.status_code == 401


def test_chat_with_the_wrong_token_is_rejected(client, fake_core, monkeypatch) -> None:
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    response = client.post(
        "/chat",
        json={"message": "test"},
        headers={"Authorization": "Bearer mauvais-jeton"},
    )
    assert response.status_code == 401


def test_chat_with_the_right_token_succeeds(client, fake_core, monkeypatch) -> None:
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    response = client.post(
        "/chat",
        json={"message": "test"},
        headers={"Authorization": "Bearer secret123"},
    )
    assert response.status_code == 200


def test_history_and_system_also_require_the_token(client, fake_core, monkeypatch) -> None:
    """
    Pas seulement /chat : /history (tout l'historique) et /system (titre
    de fenêtre active, aussi révélateur qu'un nom de fichier ouvert)
    exposent chacun quelque chose de sensible.
    """
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    assert client.get("/history").status_code == 401
    assert client.get("/system").status_code == 401


def test_no_token_configured_means_no_token_required(client, fake_core) -> None:
    """
    Le comportement par défaut, sans API_TOKEN dans .env : identique à
    avant que ce mécanisme existe. Aucune régression pour Cyril tant
    qu'il n'a rien renseigné.
    """
    assert client.post("/chat", json={"message": "test"}).status_code == 200
    assert client.get("/history").status_code == 200
    assert client.get("/system").status_code == 200


def test_websocket_without_token_is_closed_once_one_is_set(client, monkeypatch) -> None:
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    with pytest.raises(Exception):
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()


def test_websocket_with_the_right_token_in_the_query_string_succeeds(client, monkeypatch) -> None:
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    with client.websocket_connect("/ws?token=secret123") as ws:
        first = _next_of_type(ws, "avatar_state")
    assert first["state"] == "idle"


def test_websocket_without_token_configured_still_works(client) -> None:
    """Comportement par défaut, jeton non configuré : inchangé."""
    with client.websocket_connect("/ws") as ws:
        first = _next_of_type(ws, "avatar_state")
    assert first["state"] == "idle"


# ── WebSocket : image (pont mobile, Phase 4) ───────────────────────────
#
# Photo envoyée par le téléphone (pas de caméra sur le PC — voir
# VISION_LONG_TERME.md §2 Pilier 3). LucasCore est doublé (fake_core) :
# ces tests vérifient le CHEMIN serveur — décodage, témoin WATCHING,
# nettoyage du fichier temporaire — pas la qualité de l'OCR/VLM, qui a
# ses propres tests dans test_vision_routing.py.

FAKE_IMAGE_B64 = base64.b64encode(b"fausses donnees d'image, jamais un vrai jpeg").decode()


def test_websocket_image_is_analyzed_and_answered(client, fake_core) -> None:
    """Le cycle attendu : watching → speaking → idle, pas listening (audio only)."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "image", "image_base64": FAKE_IMAGE_B64})

        states = []
        answer = None
        for _ in range(20):
            message = ws.receive_json()
            if message.get("type") == "avatar_state":
                states.append(message["state"])
                if message["state"] == "speaking":
                    answer = message.get("text", "")
            if states[-3:] == ["watching", "speaking", "idle"]:
                break

    assert states[-3:] == ["watching", "speaking", "idle"]
    assert answer is not None


def test_websocket_image_without_caption_uses_a_default(client, fake_core) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "image", "image_base64": FAKE_IMAGE_B64})
        _next_of_type(ws, "chat")

    assert fake_core["asked"] == "Décris ce que tu vois."


def test_websocket_image_with_a_caption_uses_it(client, fake_core) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json(
            {"type": "image", "image_base64": FAKE_IMAGE_B64, "text": "c'est quoi ce panneau ?"}
        )
        _next_of_type(ws, "chat")

    assert fake_core["asked"] == "c'est quoi ce panneau ?"


def test_websocket_image_reaches_lucas_core_with_a_real_path(client, fake_core) -> None:
    """
    Le fichier temporaire doit exister PENDANT l'appel — c'est de là que
    LucasCore._describe_camera_image() lit l'image.
    """
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "image", "image_base64": FAKE_IMAGE_B64})
        _next_of_type(ws, "chat")

    assert fake_core["asked_image_path"] is not None
    assert fake_core["image_existed_during_call"] is True


def test_websocket_image_temp_file_is_deleted_after_use(client, fake_core) -> None:
    """
    Ce sont potentiellement des photos de documents personnels : elles ne
    doivent pas traîner dans le dossier temporaire du système au-delà de
    l'appel — même principe que pour les PDF scannés (memory/index_documents.py).
    """
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "image", "image_base64": FAKE_IMAGE_B64})
        _next_of_type(ws, "chat")

    path = fake_core["asked_image_path"]
    assert not os.path.exists(path)


def test_websocket_ignores_image_without_the_field(client, fake_core) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "image"})
        ws.send_json({"type": "chat", "message": "vrai message"})
        message = _next_of_type(ws, "chat", limit=20)

    assert "vrai message" in message["text"]


def test_websocket_bad_base64_image_reports_an_error_not_a_crash(client, fake_core) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "image", "image_base64": "!!! pas du base64 valide !!!"})
        error = _next_of_type(ws, "error")
        idle = _next_of_type(ws, "avatar_state")

    assert "Image illisible" in error["detail"]
    assert idle["state"] == "idle"


# ── PWA statique ────────────────────────────────────────────────────────

def test_pwa_index_is_served(client) -> None:
    response = client.get("/app/")
    assert response.status_code == 200
    assert "manifest.json" in response.text


def test_pwa_manifest_is_served(client) -> None:
    response = client.get("/app/manifest.json")
    assert response.status_code == 200
    assert response.json()["name"] == "Luca's"


def test_pwa_does_not_shadow_the_json_api(client) -> None:
    """Le mount /app est déclaré en dernier : les routes JSON doivent rester atteignables."""
    assert client.get("/status").status_code == 200


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
