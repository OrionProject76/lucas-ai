# test_ollama_client.py — reprise sur 404 et diagnostic
#
# Des « 404 model not found » intermittents apparaissaient au démarrage,
# sur un modèle pourtant listé par `ollama list`. La cause n'était pas le
# doublon d'instances (déjà traité) mais la résolution implicite du tag :
# « qwen2.5 » ne correspond exactement à aucun modèle, Ollama devine
# « qwen2.5:latest », et cette résolution échoue tant que son registre
# n'est pas chargé.
#
# Aucun appel réseau : requests est mocké.

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core import ollama_client
from core.ollama_client import OllamaModelMissing, is_ready, post_chat

PAYLOAD = {"model": "qwen2.5:7b", "messages": [{"role": "user", "content": "x"}]}


def _response(status: int):
    return SimpleNamespace(
        status_code=status,
        raise_for_status=lambda: None,
        json=lambda: {"message": {"content": "ok"}},
    )


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    """La pause de reprise ne doit pas ralentir la suite."""
    monkeypatch.setattr(ollama_client.time, "sleep", lambda _s: None)


def test_a_transient_404_is_retried(monkeypatch) -> None:
    """Ollama répond avant d'avoir fini de charger son registre."""
    statuses = iter([404, 200])
    calls: list[dict] = []

    def fake_post(url, json=None, stream=False, timeout=None):
        calls.append(json)
        return _response(next(statuses))

    monkeypatch.setattr(ollama_client.requests, "post", fake_post)

    response = post_chat("http://x/api/chat", PAYLOAD, timeout=10)
    assert response.status_code == 200
    assert len(calls) == 2, "la requête doit être rejouée une fois"


def test_a_persistent_404_names_the_model(monkeypatch) -> None:
    """
    Un « 404 » brut n'apprend rien. Le message doit dire quel modèle
    manque et comment l'installer.
    """
    monkeypatch.setattr(
        ollama_client.requests, "post",
        lambda url, json=None, stream=False, timeout=None: _response(404),
    )

    with pytest.raises(OllamaModelMissing) as error:
        post_chat("http://x/api/chat", PAYLOAD, timeout=10)

    message = str(error.value)
    assert "qwen2.5:7b" in message
    assert "ollama pull" in message
    assert "tasklist" in message, "le doublon d'instances doit être rappelé"


def test_a_successful_call_is_not_retried(monkeypatch) -> None:
    calls: list[int] = []

    def fake_post(url, json=None, stream=False, timeout=None):
        calls.append(1)
        return _response(200)

    monkeypatch.setattr(ollama_client.requests, "post", fake_post)

    post_chat("http://x/api/chat", PAYLOAD, timeout=10)
    assert len(calls) == 1


def test_streaming_flag_is_forwarded(monkeypatch) -> None:
    """Le chat de l'UI est en streaming : l'option ne doit pas se perdre."""
    seen: dict = {}

    def fake_post(url, json=None, stream=False, timeout=None):
        seen["stream"] = stream
        return _response(200)

    monkeypatch.setattr(ollama_client.requests, "post", fake_post)

    post_chat("http://x/api/chat", PAYLOAD, timeout=10, stream=True)
    assert seen["stream"] is True


# ── Disponibilité ─────────────────────────────────────────────────────

def test_ready_when_models_are_registered(monkeypatch) -> None:
    monkeypatch.setattr(
        ollama_client.requests, "get",
        lambda url, timeout=None: SimpleNamespace(json=lambda: {"models": [{"name": "a"}]}),
    )
    assert is_ready("http://x")


def test_not_ready_when_the_registry_is_empty(monkeypatch) -> None:
    """
    Ollama répond mais n'a encore aucun modèle : c'est exactement la
    fenêtre où les 404 se produisaient.
    """
    monkeypatch.setattr(
        ollama_client.requests, "get",
        lambda url, timeout=None: SimpleNamespace(json=lambda: {"models": []}),
    )
    assert not is_ready("http://x")


def test_not_ready_when_ollama_is_down(monkeypatch) -> None:
    def refused(url, timeout=None):
        raise ConnectionError("refusé")

    monkeypatch.setattr(ollama_client.requests, "get", refused)
    assert not is_ready("http://x")


# ── Configuration ─────────────────────────────────────────────────────

def test_model_name_is_explicitly_tagged() -> None:
    """
    Un nom sans tag oblige Ollama à deviner, et cette résolution échoue
    au démarrage. C'était la cause des 404 intermittents.
    """
    from config import MODEL_NAME, VLM_MODEL

    assert ":" in MODEL_NAME, f"MODEL_NAME doit porter un tag explicite : {MODEL_NAME}"
    assert VLM_MODEL, "le modèle vision doit être défini"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
