# test_rag_manager.py — modules/rag_manager.py n'avait aucun fichier de
# test dédié (trouvé via mesure de couverture réelle, Priorité 3
# qualité/fiabilité, 04/08/2026). Portée volontairement étroite : juste
# OllamaEmbeddingFunction.__call__(), jamais exercée par aucun test
# existant (les tests de RAG passent tous par des collections/managers
# déjà mockés — voir test_semantic_desktop.py, demos/calibrate_rag.py).
# Une couverture complète de RAGManager (ChromaDB réel) est un chantier
# plus large, hors de ce qui est traité ici.

from __future__ import annotations

import pytest

from modules.rag_manager import OllamaEmbeddingFunction


class _FakeEmbeddingResponse:
    def __init__(self, embedding: list[float]) -> None:
        self._embedding = embedding

    def json(self):
        return {"embedding": self._embedding}


def test_embeds_a_single_text(monkeypatch) -> None:
    """
    ⚠️ chromadb enveloppe le retour de EmbeddingFunction.__call__ en
    numpy.ndarray (float32) — comparer via list()/round() plutôt que ==
    directement, sinon "truth value of an array is ambiguous".
    """
    monkeypatch.setattr(
        "modules.rag_manager.requests.post",
        lambda *a, **k: _FakeEmbeddingResponse([0.1, 0.2, 0.3]),
    )
    result = OllamaEmbeddingFunction()(["bonjour"])
    assert len(result) == 1
    assert [round(float(x), 1) for x in result[0]] == [0.1, 0.2, 0.3]


def test_embeds_each_text_separately_and_preserves_order(monkeypatch) -> None:
    calls: list[str] = []

    def _fake_post(url, json):
        calls.append(json["prompt"])
        return _FakeEmbeddingResponse([float(len(json["prompt"]))])

    monkeypatch.setattr("modules.rag_manager.requests.post", _fake_post)
    result = OllamaEmbeddingFunction()(["a", "bb", "ccc"])

    assert calls == ["a", "bb", "ccc"]
    assert [list(vec) for vec in result] == [[1.0], [2.0], [3.0]]


def test_calls_the_ollama_embeddings_endpoint_with_the_right_model(monkeypatch) -> None:
    from config import OLLAMA_HOST

    captured = {}

    def _fake_post(url, json):
        captured["url"] = url
        captured["model"] = json["model"]
        return _FakeEmbeddingResponse([0.0])

    monkeypatch.setattr("modules.rag_manager.requests.post", _fake_post)
    OllamaEmbeddingFunction()(["texte"])

    assert captured["url"] == f"{OLLAMA_HOST}/api/embeddings"
    assert captured["model"] == "nomic-embed-text"


def test_a_failed_embedding_call_raises_a_clear_french_error(monkeypatch) -> None:
    def _raise(*a, **k):
        raise ConnectionError("Ollama injoignable")

    monkeypatch.setattr("modules.rag_manager.requests.post", _raise)

    with pytest.raises(RuntimeError, match="ollama serve"):
        OllamaEmbeddingFunction()(["texte"])


def test_a_malformed_response_also_raises_a_clear_error(monkeypatch) -> None:
    """Une réponse sans la clé "embedding" ne doit jamais lever une KeyError brute."""
    class _BrokenResponse:
        def json(self):
            return {"unexpected": "shape"}

    monkeypatch.setattr(
        "modules.rag_manager.requests.post", lambda *a, **k: _BrokenResponse()
    )

    with pytest.raises(RuntimeError, match="Échec de l'embedding Ollama"):
        OllamaEmbeddingFunction()(["texte"])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
