# test_router.py — vérifie le routage local/cloud et ce qui est joint au cloud
#
# Règle testée : le local gagne toujours en cas de conflit (CLAUDE.md règle 3).
# Se lance avec pytest, ou directement : python test_router.py

from __future__ import annotations

import pytest

from config import CLOUD_HISTORY_MESSAGES
from core.router import (
    is_sensitive,
    mentions_pc_explicitly,
    route,
    should_use_rag,
    should_use_vision,
)

# core.lucas_core tire chromadb (via modules/rag_manager). Les tests de routage
# n'en ont pas besoin : on les garde exécutables même sur un environnement
# minimal, et on saute seulement les tests de _build_messages.
try:
    from core import lucas_core
    from core.lucas_core import LucasCore

    CORE_AVAILABLE = True
except ModuleNotFoundError as exc:  # pragma: no cover
    CORE_AVAILABLE = False
    CORE_IMPORT_ERROR = str(exc)

requires_core = pytest.mark.skipif(
    not CORE_AVAILABLE,
    reason="core.lucas_core indisponible (dépendance manquante)",
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


# ── Robustesse de la saisie réelle ────────────────────────────────────
#
# Ces cas viennent d'un test en conditions réelles, pas d'une revue de
# code : « qu'est-ce que tu vois à l'écran » ne déclenchait pas la vision
# quand l'apostrophe était typographique, et — bien plus grave — une
# question financière tapée sans accents partait au CLOUD.

@pytest.mark.parametrize(
    "question",
    [
        "analyse mes dépenses du mois",
        "analyse mes depenses du mois",
        "compare mon relevé bancaire",
        "compare mon releve bancaire",
        "analyse mon crédit immobilier",
        "analyse mon credit immobilier",
        "ANALYSE MES DEPENSES",
    ],
)
def test_accents_do_not_defeat_the_sensitive_guard(question: str) -> None:
    """
    Taper vite, sans accents, suffisait à envoyer une question financière
    au cloud : « depense » ne correspondait pas au mot-clé « dépense ».
    La règle 3 était rendue inopérante par une faute de frappe.
    """
    assert is_sensitive(question), f"« {question} » doit être reconnu comme sensible"
    assert route(question) == "local"


@pytest.mark.parametrize(
    "question",
    [
        "qu'est-ce que tu vois à l'écran ?",
        "qu'est ce que tu vois à l'écran ?",
        "qu’est ce que tu vois à l’écran ?",
        "qu'est ce que tu vois a l'ecran",
        "QU'EST CE QUE TU VOIS À L'ÉCRAN",
    ],
)
def test_apostrophes_and_accents_do_not_defeat_vision(question: str) -> None:
    """
    L'apostrophe typographique « ’ » que produisent Windows et les
    correcteurs ne correspondait pas à l'apostrophe droite des mots-clés.
    La question la plus naturelle pour demander la vision ne déclenchait
    donc rien.
    """
    assert should_use_vision(question)
    assert route(question) == "local"


def test_normalisation_is_shared_by_every_keyword_list() -> None:
    """
    Garde anti-régression : toute comparaison de mots-clés doit passer
    par core.text_utils, sinon la faille revient sur une liste oubliée.
    """
    import inspect

    from core import router

    source = inspect.getsource(router)
    assert "contains_any" in source
    assert ".lower()" not in source, (
        "une comparaison en minuscules seule ignore accents et apostrophes"
    )


# ── _build_messages() ─────────────────────────────────────────────────

class _FakeMemory:
    """Remplace MemoryManager sans toucher à SQLite."""

    def __init__(self, history: list[tuple[str, str]]) -> None:
        self._history = history

    def load_history(self) -> list[tuple[str, str]]:
        return self._history

    def load_recent_events(self, limit: int = 5) -> list[tuple[str, str, str]]:
        """Mémoire enrichie : pas d'événement ici, ces tests portent sur le RAG
        et l'historique. Voir test_memory_context.py pour les événements."""
        return []


@pytest.fixture
def core_with_history(monkeypatch) -> LucasCore:
    """LucasCore sans base ni World Model, avec 40 messages d'historique."""
    monkeypatch.setattr(lucas_core, "get_snapshot", dict)
    monkeypatch.setattr(
        lucas_core, "format_for_prompt",
        lambda snapshot, include_window=True: "[système]",
    )
    monkeypatch.setattr(
        lucas_core, "RAGManager", lambda: _FakeRag()
    )

    core = LucasCore.__new__(LucasCore)
    core.memory = _FakeMemory([("user", f"message {i}") for i in range(40)])
    return core


class _FakeRag:
    def get_context(self, query: str) -> str:
        return "[RAG] extrait confidentiel d'un document personnel"


@requires_core
def test_cloud_never_receives_rag_context(core_with_history: LucasCore) -> None:
    """Aucun extrait de document personnel ne doit atteindre le cloud."""
    messages = core_with_history._build_messages("résume le document", "cloud")
    assert not any("[RAG]" in m["content"] for m in messages)


@requires_core
def test_local_receives_rag_context(core_with_history: LucasCore) -> None:
    """En local, le RAG fonctionne toujours normalement."""
    messages = core_with_history._build_messages("résume le document", "local")
    assert any("[RAG]" in m["content"] for m in messages)


@requires_core
def test_cloud_history_is_truncated(core_with_history: LucasCore) -> None:
    """L'historique joint au cloud est réduit, pas complet."""
    messages = core_with_history._build_messages("compare ces options", "cloud")
    history = [m for m in messages if m["role"] != "system"]
    assert len(history) == CLOUD_HISTORY_MESSAGES


@requires_core
def test_local_history_is_complete(core_with_history: LucasCore) -> None:
    messages = core_with_history._build_messages("bonjour", "local")
    history = [m for m in messages if m["role"] != "system"]
    assert len(history) == 40


@requires_core
def test_default_destination_is_local(core_with_history: LucasCore) -> None:
    """Un appel sans destination ne doit jamais se comporter comme du cloud."""
    default = core_with_history._build_messages("résume le document")
    explicit = core_with_history._build_messages("résume le document", "local")
    assert default == explicit


# ── mentions_pc_explicitly() — condition de l'override mobile ─────────
#
# Ajouté le 02/08/2026 : autorise la capture d'écran PC depuis un client
# mobile SEULEMENT quand Cyril nomme le PC sans ambiguïté (voir
# core/lucas_core.py, allow_screen_capture). Mots-clés déterministes,
# même raisonnement que is_sensitive() — se tromper capturerait l'écran
# sans demande claire.

@pytest.mark.parametrize(
    "question",
    [
        "montre-moi mon PC",
        "qu'est-ce qu'il y a sur mon ordinateur",
        "regarde l'écran de mon PC",
        "regarde l'ecran de mon ordinateur",
        "c'est quoi cette erreur sur mon ordi",
        "MON PC affiche quoi",
        "sur l'ordinateur, il y a quoi",
    ],
)
def test_mentions_pc_explicitly_recognizes_the_pc(question: str) -> None:
    assert mentions_pc_explicitly(question)


@pytest.mark.parametrize(
    "question",
    [
        "que peux-tu voir sur mes écrans",
        "c'est quoi cette erreur",
        "regarde ça",
        "quelle heure il est",
        "sur mon téléphone il y a quoi",
    ],
)
def test_mentions_pc_explicitly_stays_narrow(question: str) -> None:
    """
    Volontairement étroit : "mes écrans" (pluriel, aucun appareil nommé)
    et "mon téléphone" ne doivent PAS suffire à lever la restriction —
    sinon la protection contre le déclenchement accidentel ne protège
    plus rien.
    """
    assert not mentions_pc_explicitly(question)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
