# test_cloud_llm.py — core/cloud_llm.py (API Anthropic)
#
# Aucun test ici ne parle au vrai réseau : anthropic.Anthropic est mocké
# systématiquement. cloud_usage (memory/memory_manager.py) est exercé
# réellement mais toujours sur un fichier tmp_path — jamais la vraie base
# de Cyril (voir DB_PATH monkeypatché partout où record_cloud_usage() est
# exercé).

from __future__ import annotations

import httpx
import pytest

from core import cloud_llm
from memory import memory_manager


@pytest.fixture(autouse=True)
def _isolate_cloud_usage(monkeypatch, tmp_path):
    """Toute écriture cloud_usage part sur un fichier temporaire, jamais la vraie base."""
    monkeypatch.setattr(memory_manager, "DB_PATH", tmp_path / "test_cloud_usage.db")


def _fake_response(status_code: int) -> httpx.Response:
    return httpx.Response(
        status_code, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    )


class _FakeTextBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _FakeUsage:
    def __init__(self, input_tokens: int = 10, output_tokens: int = 5) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeResponse:
    def __init__(self, text: str = "réponse", stop_reason: str = "end_turn", usage=None) -> None:
        self.content = [_FakeTextBlock(text)] if text else []
        self.stop_reason = stop_reason
        self.usage = usage or _FakeUsage()


class _FakeMessages:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._response


def _install_fake_anthropic(monkeypatch, response=None, error=None) -> _FakeMessages:
    fake_messages = _FakeMessages(response=response, error=error)

    class _Client:
        def __init__(self, api_key: str) -> None:
            self.messages = fake_messages

    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", _Client)
    monkeypatch.setattr(cloud_llm, "ANTHROPIC_API_KEY", "sk-ant-factice")
    return fake_messages


# ── Sans clé ──────────────────────────────────────────────────────────

def test_ask_cloud_returns_configuration_message_without_key(monkeypatch) -> None:
    monkeypatch.setattr(cloud_llm, "ANTHROPIC_API_KEY", "")

    reponse = cloud_llm.ask_cloud([{"role": "user", "content": "salut"}])

    assert "non configuré" in reponse.lower()
    assert "set_anthropic_key" in reponse


# ── _to_anthropic_format() ───────────────────────────────────────────────

def test_to_anthropic_format_separates_system_from_messages() -> None:
    messages = [
        {"role": "system", "content": "Tu es Luca."},
        {"role": "system", "content": "Contexte additionnel."},
        {"role": "user", "content": "bonjour"},
        {"role": "assistant", "content": "salut"},
    ]

    system, converted = cloud_llm._to_anthropic_format(messages)

    assert system == "Tu es Luca.\n\nContexte additionnel."
    assert converted == [
        {"role": "user", "content": "bonjour"},
        {"role": "assistant", "content": "salut"},
    ]


# ── Appel réel (mocké) ────────────────────────────────────────────────

def test_ask_cloud_calls_anthropic_with_the_configured_model(monkeypatch) -> None:
    import config

    fake_messages = _install_fake_anthropic(monkeypatch, response=_FakeResponse("bonjour Cyril"))

    reponse = cloud_llm.ask_cloud([{"role": "user", "content": "salut"}])

    assert reponse == "bonjour Cyril"
    assert len(fake_messages.calls) == 1
    call = fake_messages.calls[0]
    assert call["model"] == config.ANTHROPIC_MODEL
    assert call["output_config"] == {"effort": config.ANTHROPIC_EFFORT}
    assert call["max_tokens"] == config.ANTHROPIC_MAX_TOKENS


def test_ask_cloud_records_usage_in_the_cloud_usage_table(monkeypatch, tmp_path) -> None:
    _install_fake_anthropic(
        monkeypatch, response=_FakeResponse("ok", usage=_FakeUsage(input_tokens=1000, output_tokens=500))
    )

    cloud_llm.ask_cloud([{"role": "user", "content": "salut"}])

    memory = memory_manager.MemoryManager(db_path=memory_manager.DB_PATH)
    try:
        usage = memory.cloud_usage_this_month()
    finally:
        memory.close()
    assert usage["input_tokens"] == 1000
    assert usage["output_tokens"] == 500
    assert usage["cost_eur"] > 0


def test_ask_cloud_returns_an_empty_response_message_when_no_text_block(monkeypatch) -> None:
    _install_fake_anthropic(monkeypatch, response=_FakeResponse(text=""))

    reponse = cloud_llm.ask_cloud([{"role": "user", "content": "salut"}])

    assert reponse == "[Cloud] Réponse vide."


# ── Refus (garde-fous Anthropic) ─────────────────────────────────────────

def test_ask_cloud_handles_a_refusal_without_crashing(monkeypatch) -> None:
    """
    Vérifié AVANT de lire response.content : un refus des garde-fous rend
    HTTP 200 avec stop_reason="refusal" et un content vide ou partiel —
    lire content[0] sans ce test planterait (skill claude-api).
    """
    _install_fake_anthropic(
        monkeypatch, response=_FakeResponse(text="", stop_reason="refusal")
    )

    reponse = cloud_llm.ask_cloud([{"role": "user", "content": "salut"}])

    assert "refusée" in reponse.lower()


# ── Erreurs réseau/API ────────────────────────────────────────────────

def test_ask_cloud_handles_authentication_error(monkeypatch) -> None:
    import anthropic

    error = anthropic.AuthenticationError("invalide", response=_fake_response(401), body=None)
    _install_fake_anthropic(monkeypatch, error=error)

    reponse = cloud_llm.ask_cloud([{"role": "user", "content": "salut"}])

    assert "invalide" in reponse.lower() or "révoquée" in reponse.lower()


def test_ask_cloud_handles_rate_limit_error(monkeypatch) -> None:
    import anthropic

    error = anthropic.RateLimitError("trop de requêtes", response=_fake_response(429), body=None)
    _install_fake_anthropic(monkeypatch, error=error)

    reponse = cloud_llm.ask_cloud([{"role": "user", "content": "salut"}])

    assert "limite" in reponse.lower()


def test_ask_cloud_handles_connection_error(monkeypatch) -> None:
    import anthropic

    error = anthropic.APIConnectionError(
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    )
    _install_fake_anthropic(monkeypatch, error=error)

    reponse = cloud_llm.ask_cloud([{"role": "user", "content": "salut"}])

    assert "réseau" in reponse.lower() or "joindre" in reponse.lower()


def test_ask_cloud_handles_generic_api_status_error(monkeypatch) -> None:
    import anthropic

    error = anthropic.APIStatusError("panne serveur", response=_fake_response(500), body=None)
    _install_fake_anthropic(monkeypatch, error=error)

    reponse = cloud_llm.ask_cloud([{"role": "user", "content": "salut"}])

    assert "500" in reponse


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
