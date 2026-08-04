# test_local_llm.py — core/local_llm.py, jusqu'ici sans test dédié
# (trouvé via mesure de couverture réelle — 27%, Priorité 3 qualité/
# fiabilité, 04/08/2026). ask_local() est LA fonction utilisée par
# LucasCore, ReasoningEngine, finance_categorizer et core/intent.py pour
# parler à Ollama en non-streamé — mais aucun de ces appelants ne teste
# ask_local() elle-même, ils l'injectent tous comme une fausse fonction.
#
# post_chat() est mocké : aucun vrai appel réseau/Ollama ici.

from __future__ import annotations

import pytest
import requests

from config import MODEL_NAME, OLLAMA_URL
from core.local_llm import ask_local
from core.ollama_client import OllamaModelMissing


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self):
        return self._payload


@pytest.fixture
def messages():
    return [{"role": "user", "content": "bonjour"}]


def test_successful_call_returns_the_content(monkeypatch, messages) -> None:
    monkeypatch.setattr(
        "core.local_llm.post_chat",
        lambda *a, **k: _FakeResponse({"message": {"content": "Bonjour Cyril !"}}),
    )
    assert ask_local(messages) == "Bonjour Cyril !"


def test_calls_the_configured_model_and_url_non_streamed(monkeypatch, messages) -> None:
    """Vérifie ce qui est réellement envoyé — pas juste ce qui revient."""
    captured = {}

    def _fake_post_chat(url, payload, timeout):
        captured["url"] = url
        captured["payload"] = payload
        captured["timeout"] = timeout
        return _FakeResponse({"message": {"content": "ok"}})

    monkeypatch.setattr("core.local_llm.post_chat", _fake_post_chat)
    ask_local(messages)

    assert captured["url"] == OLLAMA_URL
    assert captured["payload"]["model"] == MODEL_NAME
    assert captured["payload"]["messages"] == messages
    assert captured["payload"]["stream"] is False


def test_model_missing_returns_a_clear_french_error(monkeypatch, messages) -> None:
    def _raise(*a, **k):
        raise OllamaModelMissing(f"Modèle « {MODEL_NAME} » introuvable pour Ollama.")

    monkeypatch.setattr("core.local_llm.post_chat", _raise)
    result = ask_local(messages)

    assert result.startswith("[Erreur]")
    assert "introuvable" in result


def test_connection_error_names_ollama_serve(monkeypatch, messages) -> None:
    """
    ⚠️ Message spécifique et volontaire : dire à Cyril la commande exacte
    (`ollama serve`) plutôt qu'une erreur réseau générique.
    """
    def _raise(*a, **k):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr("core.local_llm.post_chat", _raise)
    result = ask_local(messages)

    assert result.startswith("[Erreur]")
    assert "ollama serve" in result
    assert OLLAMA_URL in result


def test_other_request_exceptions_are_reported_as_network_problems(monkeypatch, messages) -> None:
    """
    Distinct de ConnectionError : un timeout ou une erreur HTTP générique
    tombe dans la branche RequestException plus large, pas la branche
    "Ollama injoignable" spécifique.
    """
    def _raise(*a, **k):
        raise requests.exceptions.Timeout("trop long")

    monkeypatch.setattr("core.local_llm.post_chat", _raise)
    result = ask_local(messages)

    assert result.startswith("[Erreur] Problème réseau avec Ollama")


def test_missing_message_key_is_reported_as_unexpected_response(monkeypatch, messages) -> None:
    """Une réponse Ollama sans la clé "message" ne doit jamais lever jusqu'à l'appelant."""
    monkeypatch.setattr(
        "core.local_llm.post_chat", lambda *a, **k: _FakeResponse({"unexpected": "shape"})
    )
    result = ask_local(messages)

    assert result.startswith("[Erreur]")
    assert MODEL_NAME in result
    assert "ollama list" in result


def test_invalid_json_is_reported_as_unexpected_response(monkeypatch, messages) -> None:
    class _BrokenJSON:
        def json(self):
            raise ValueError("pas du JSON valide")

    monkeypatch.setattr("core.local_llm.post_chat", lambda *a, **k: _BrokenJSON())
    result = ask_local(messages)

    assert result.startswith("[Erreur]")
    assert "inattendue" in result


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
