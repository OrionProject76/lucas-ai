# test_llm_worker.py — core/llm_worker.py, jusqu'ici sans aucun test
# (trouvé en auditant la couverture, Priorité 3 qualité/fiabilité,
# 03-04/08/2026). Même famille que test_ui_workers.py::ContextWorker :
# `.run()` est appelé directement (pas de vraie boucle Qt nécessaire),
# post_chat() est mocké, aucun vrai appel réseau/Ollama.

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from core.llm_worker import LLMWorker
from core.ollama_client import OllamaModelMissing


class _FakeStreamResponse:
    """Imite requests.Response.iter_lines() — pas de vrai réseau."""

    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines

    def iter_lines(self):
        return iter(self._lines)


def _chunk(content: str = "", done: bool = False) -> bytes:
    return json.dumps({"message": {"content": content}, "done": done}).encode()


@pytest.fixture
def messages():
    return [{"role": "user", "content": "bonjour"}]


def test_successful_stream_emits_tokens_and_final_response(monkeypatch, messages) -> None:
    lines = [_chunk("Bon"), _chunk("jour"), _chunk(" !", done=True)]
    monkeypatch.setattr(
        "core.llm_worker.post_chat", lambda *a, **k: _FakeStreamResponse(lines)
    )

    worker = LLMWorker(messages)
    tokens: list[str] = []
    complete: list[str] = []
    worker.token_received.connect(tokens.append)
    worker.response_complete.connect(complete.append)
    worker.run()

    assert tokens == ["Bon", "jour", " !"]
    assert complete == ["Bonjour !"]


def test_started_thinking_is_emitted_once_connection_is_established(monkeypatch, messages) -> None:
    monkeypatch.setattr(
        "core.llm_worker.post_chat",
        lambda *a, **k: _FakeStreamResponse([_chunk("ok", done=True)]),
    )

    worker = LLMWorker(messages)
    started: list[None] = []
    worker.started_thinking.connect(lambda: started.append(None))
    worker.run()

    assert started == [None]


def test_stop_halts_further_tokens(monkeypatch, messages) -> None:
    """
    ⚠️ `stop()` positionne juste le drapeau — dans `run()` (appelé
    directement ici, sans thread réel), il faut le lever DEPUIS la
    boucle elle-même pour observer l'arrêt, comme le ferait un clic sur
    "stop" pendant qu'un vrai thread tourne encore.
    """
    worker = LLMWorker(messages)
    tokens: list[str] = []
    worker.token_received.connect(tokens.append)

    lines = [_chunk("un"), _chunk("deux"), _chunk("trois", done=True)]

    def _stopping_after_first(*a, **k):
        class _StoppingResponse(_FakeStreamResponse):
            def iter_lines(self_inner):
                for i, line in enumerate(lines):
                    if i == 1:
                        worker._is_running = False
                    yield line

        return _StoppingResponse(lines)

    monkeypatch.setattr("core.llm_worker.post_chat", _stopping_after_first)
    worker.run()

    assert tokens == ["un"], "aucun token après l'arrêt ne doit être émis"


def test_model_missing_emits_a_clear_error(monkeypatch, messages) -> None:
    def _raise(*a, **k):
        raise OllamaModelMissing("Modèle « qwen2.5:7b » introuvable pour Ollama.")

    monkeypatch.setattr("core.llm_worker.post_chat", _raise)

    worker = LLMWorker(messages)
    errors: list[str] = []
    worker.error_occurred.connect(errors.append)
    worker.run()

    assert errors and errors[0].startswith("[Erreur]")
    assert "introuvable" in errors[0]


def test_connection_error_emits_a_clear_error(monkeypatch, messages) -> None:
    import requests

    def _raise(*a, **k):
        raise requests.exceptions.ConnectionError("boum")

    monkeypatch.setattr("core.llm_worker.post_chat", _raise)

    worker = LLMWorker(messages)
    errors: list[str] = []
    worker.error_occurred.connect(errors.append)
    worker.run()

    assert errors and "Impossible de contacter Ollama" in errors[0]


def test_read_timeout_emits_a_clear_error(monkeypatch, messages) -> None:
    import requests

    def _raise(*a, **k):
        raise requests.exceptions.ReadTimeout("trop long")

    monkeypatch.setattr("core.llm_worker.post_chat", _raise)

    worker = LLMWorker(messages)
    errors: list[str] = []
    worker.error_occurred.connect(errors.append)
    worker.run()

    assert errors and "trop de temps" in errors[0]


def test_malformed_json_line_is_skipped_not_crashed(monkeypatch, messages) -> None:
    """Une ligne mal formée ne doit pas faire planter le flux — juste être ignorée."""
    lines = [b"pas du json", _chunk("valide", done=True)]
    monkeypatch.setattr(
        "core.llm_worker.post_chat", lambda *a, **k: _FakeStreamResponse(lines)
    )

    worker = LLMWorker(messages)
    complete: list[str] = []
    worker.response_complete.connect(complete.append)
    worker.run()  # ne doit pas lever

    assert complete == ["valide"]


def test_empty_lines_are_skipped(monkeypatch, messages) -> None:
    lines = [b"", _chunk("ok", done=True)]
    monkeypatch.setattr(
        "core.llm_worker.post_chat", lambda *a, **k: _FakeStreamResponse(lines)
    )

    worker = LLMWorker(messages)
    complete: list[str] = []
    worker.response_complete.connect(complete.append)
    worker.run()

    assert complete == ["ok"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
