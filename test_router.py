# test_router.py — vérifie le routage local/cloud et ce qui est joint au cloud
#
# Règle testée : le local gagne toujours en cas de conflit (CLAUDE.md règle 3).
# Se lance avec pytest, ou directement : python test_router.py

from __future__ import annotations

import pytest

from config import CLOUD_HISTORY_MESSAGES
from core.router import is_sensitive, route, should_use_rag

# core.orion_core tire chromadb (via modules/rag_manager). Les tests de routage
# n'en ont pas besoin : on les garde exécutables même sur un environnement
# minimal, et on saute seulement les tests de _build_messages.
try:
    from core import orion_core
    from core.orion_core import OrionCore

    CORE_AVAILABLE = True
except ModuleNotFoundError as exc:  # pragma: no cover
    CORE_AVAILABLE = False
    CORE_IMPORT_ERROR = str(exc)

requires_core = pytest.mark.skipif(
    not CORE_AVAILABLE,
    reason="core.orion_core indisponible (dépendance manquante)",
)


# ── route() ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "question, expected, why",
    [
        ("analyse mon portfolio", "local", "sensible bat cloud"),
        ("fais une projection sur 20 ans", "cloud", "question complexe"),
        ("résume le document et analyse-le", "local", "RAG bat cloud"),
        ("quelle heure il est", "local", "défaut sûr"),
        ("compare ces deux stratégies", "cloud", "question complexe"),
        ("mes dépenses du mois", "local", "sensible"),
        ("ANALYSE MON BUDGET", "local", "insensible à la casse"),
        ("optimise mon crédit immobilier", "local", "sensible bat cloud"),
    ],
)
def test_route(question: str, expected: str, why: str) -> None:
    assert route(question) == expected, f"« {question} » devrait être {expected} ({why})"


def test_sensitive_beats_cloud_keyword() -> None:
    """Le cas central : les deux listes matchent, le local doit gagner."""
    question = "analyse mon portfolio"
    assert is_sensitive(question)
    assert route(question) == "local"


def test_rag_beats_cloud_keyword() -> None:
    """Un document personnel ne part jamais au cloud, même sur une analyse."""
    question = "résume le document et analyse-le"
    assert should_use_rag(question)
    assert route(question) == "local"


# ── _build_messages() ─────────────────────────────────────────────────

class _FakeMemory:
    """Remplace MemoryManager sans toucher à SQLite."""

    def __init__(self, history: list[tuple[str, str]]) -> None:
        self._history = history

    def load_history(self) -> list[tuple[str, str]]:
        return self._history


@pytest.fixture
def core_with_history(monkeypatch) -> "OrionCore":
    """OrionCore sans base ni World Model, avec 40 messages d'historique."""
    monkeypatch.setattr(orion_core, "get_snapshot", lambda: {})
    monkeypatch.setattr(orion_core, "format_for_prompt", lambda snapshot: "[système]")
    monkeypatch.setattr(
        orion_core, "RAGManager", lambda: _FakeRag()
    )

    core = OrionCore.__new__(OrionCore)
    core.memory = _FakeMemory([("user", f"message {i}") for i in range(40)])
    return core


class _FakeRag:
    def get_context(self, query: str) -> str:
        return "[RAG] extrait confidentiel d'un document personnel"


@requires_core
def test_cloud_never_receives_rag_context(core_with_history: OrionCore) -> None:
    """Aucun extrait de document personnel ne doit atteindre le cloud."""
    messages = core_with_history._build_messages("résume le document", "cloud")
    assert not any("[RAG]" in m["content"] for m in messages)


@requires_core
def test_local_receives_rag_context(core_with_history: OrionCore) -> None:
    """En local, le RAG fonctionne toujours normalement."""
    messages = core_with_history._build_messages("résume le document", "local")
    assert any("[RAG]" in m["content"] for m in messages)


@requires_core
def test_cloud_history_is_truncated(core_with_history: OrionCore) -> None:
    """L'historique joint au cloud est réduit, pas complet."""
    messages = core_with_history._build_messages("compare ces options", "cloud")
    history = [m for m in messages if m["role"] != "system"]
    assert len(history) == CLOUD_HISTORY_MESSAGES


@requires_core
def test_local_history_is_complete(core_with_history: OrionCore) -> None:
    messages = core_with_history._build_messages("bonjour", "local")
    history = [m for m in messages if m["role"] != "system"]
    assert len(history) == 40


@requires_core
def test_default_destination_is_local(core_with_history: OrionCore) -> None:
    """Un appel sans destination ne doit jamais se comporter comme du cloud."""
    default = core_with_history._build_messages("résume le document")
    explicit = core_with_history._build_messages("résume le document", "local")
    assert default == explicit


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
