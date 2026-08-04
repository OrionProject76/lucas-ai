# test_router.py — vérifie le routage local/cloud et ce qui est joint au cloud
#
# Règle testée : le local gagne toujours en cas de conflit (CLAUDE.md règle 3).
# Se lance avec pytest, ou directement : python test_router.py

from __future__ import annotations

import pytest

from config import CLOUD_HISTORY_MESSAGES
from core.router import (
    extract_calculation,
    is_sensitive,
    mentions_pc_explicitly,
    route,
    should_use_calculator,
    should_use_finance,
    should_use_rag,
    should_use_vision,
    should_use_websearch,
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


# ── should_use_finance() ────────────────────────────────────────────────

@pytest.mark.parametrize(
    "question",
    [
        "quel est mon solde ?",
        "résume mes finances",
        "combien j'ai dépensé ce mois-ci",
        "MES DÉPENSES du mois",
        "quel est mon solde",  # sans accent ni apostrophe typographique
        "mon budget est de combien",
    ],
)
def test_should_use_finance_detects_finance_questions(question: str) -> None:
    assert should_use_finance(question)


@pytest.mark.parametrize(
    "question",
    ["quelle heure est-il ?", "résume le document", "explique-moi la photosynthèse"],
)
def test_should_use_finance_ignores_unrelated_questions(question: str) -> None:
    assert not should_use_finance(question)


# ── should_use_calculator() / extract_calculation() (câblé 04/08/2026) ──

@pytest.mark.parametrize(
    "question",
    [
        "combien font 45 + 32 ?",
        "combien fait 10 * (3 + 2)",
        "calcule 100 / 4",
        "quel est le resultat de 7 - 2 ?",
    ],
)
def test_should_use_calculator_detects_real_expressions(question: str) -> None:
    assert should_use_calculator(question)


@pytest.mark.parametrize(
    "question",
    [
        "quelle heure est-il ?",
        "combien font mes economies",  # mot-clé présent, aucune expression
        "resume le document",
    ],
)
def test_should_use_calculator_ignores_unrelated_or_expressionless_questions(question: str) -> None:
    assert not should_use_calculator(question)


def test_extract_calculation_finds_the_expression_in_natural_language() -> None:
    assert extract_calculation("combien font 45 + 32 ?") == "45 + 32"


def test_extract_calculation_ignores_a_single_number() -> None:
    """Un seul nombre n'est pas une expression — rien à calculer."""
    assert extract_calculation("il est 15h") is None


def test_extract_calculation_returns_none_without_an_operator() -> None:
    assert extract_calculation("2026") is None


# ── should_use_websearch() (câblé 04/08/2026) ────────────────────────────

@pytest.mark.parametrize(
    "question",
    [
        "cherche sur internet la recette de la tarte tatin",
        "recherche sur le web les horaires du musée",
        "cherche en ligne qui a gagné le match hier",
        "CHERCHE SUR LE WEB des infos sur ce sujet",
    ],
)
def test_should_use_websearch_detects_explicit_requests(question: str) -> None:
    assert should_use_websearch(question)


@pytest.mark.parametrize(
    "question",
    [
        "quelle heure est-il ?",
        "qui a inventé la tour Eiffel",  # question générale, pas de demande explicite
        "resume le document",
    ],
)
def test_should_use_websearch_ignores_implicit_general_knowledge_questions(question: str) -> None:
    """
    Volontairement étroit : contrairement au RAG/vision, aucun mot-clé
    fiable ne distingue une question de connaissance générale d'une
    question ordinaire — seule une demande EXPLICITE déclenche la recherche.
    """
    assert not should_use_websearch(question)


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

    def load_history_with_metadata(self) -> list[dict]:
        return [
            {"role": r, "message": m, "confidence": 1.0, "importance": 0.5, "expiration": None}
            for r, m in self._history
        ]

    def load_recent_events(self, limit: int = 5) -> list[tuple[str, str, str]]:
        """Mémoire enrichie : pas d'événement ici, ces tests portent sur le RAG
        et l'historique. Voir test_memory_context.py pour les événements."""
        return []

    def load_recent_events_with_metadata(self, limit: int = 5) -> list[dict]:
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


# ── Finance CSV (03/08/2026) ─────────────────────────────────────────────

class _FakeFinanceManager:
    def __init__(self, transactions: list, summary: str) -> None:
        self.transactions = transactions
        self._summary = summary

    def get_summary(self) -> str:
        return self._summary


@requires_core
def test_cloud_never_receives_finance_context(core_with_history: LucasCore, monkeypatch) -> None:
    """
    Un solde ou une dépense réelle ne doit jamais atteindre le cloud.

    Monkeypatché sur "modules.finance_manager.load_directory", pas
    "lucas_core.load_directory" : l'import est PARESSEUX (voir en-tête de
    core/lucas_core.py, même motif que core.dates) — il n'existe donc pas
    en tant qu'attribut du module lucas_core.
    """
    monkeypatch.setattr(
        "modules.finance_manager.load_directory",
        lambda: (_FakeFinanceManager([{"montant": -10.0}], "[FINANCE] solde réel"), []),
    )
    messages = core_with_history._build_messages("quel est mon solde ?", "cloud")
    assert not any("[FINANCE]" in m["content"] for m in messages)


@requires_core
def test_local_receives_finance_context_when_data_exists(core_with_history: LucasCore, monkeypatch) -> None:
    monkeypatch.setattr(
        "modules.finance_manager.load_directory",
        lambda: (_FakeFinanceManager([{"montant": -10.0}], "[FINANCE] solde réel"), []),
    )
    messages = core_with_history._build_messages("quel est mon solde ?", "local")
    assert any("[FINANCE]" in m["content"] for m in messages)


@requires_core
def test_finance_context_says_no_data_explicitly_when_empty(core_with_history: LucasCore, monkeypatch) -> None:
    """Même bug que le RAG sans résultat : ne jamais laisser le modèle deviner un solde."""
    monkeypatch.setattr(
        "modules.finance_manager.load_directory",
        lambda: (_FakeFinanceManager([], "vide"), []),
    )
    messages = core_with_history._build_messages("quel est mon solde ?", "local")
    joined = " ".join(m["content"] for m in messages)
    assert "AUCUNE TRANSACTION IMPORTÉE" in joined
    assert "INTERDIT" in joined


@requires_core
def test_finance_context_absent_when_question_unrelated(core_with_history: LucasCore, monkeypatch) -> None:
    """Pas de bruit de dossier vide sur une question qui n'a rien à voir."""
    monkeypatch.setattr(
        "modules.finance_manager.load_directory",
        lambda: (_FakeFinanceManager([], "vide"), []),
    )
    messages = core_with_history._build_messages("bonjour", "local")
    assert not any("RELEVÉS BANCAIRES" in m["content"] for m in messages)
    assert not any("AUCUNE TRANSACTION" in m["content"] for m in messages)


# ── Calculatrice (04/08/2026) ─────────────────────────────────────────

@requires_core
def test_cloud_never_receives_calculation_context(core_with_history: LucasCore) -> None:
    messages = core_with_history._build_messages("combien font 45 + 32 ?", "cloud")
    assert not any("CALCUL RÉEL" in m["content"] for m in messages)


@requires_core
def test_local_receives_the_real_calculation_result(core_with_history: LucasCore) -> None:
    """Le résultat est calculé en Python, jamais deviné par le LLM."""
    messages = core_with_history._build_messages("combien font 45 + 32 ?", "local")
    joined = " ".join(m["content"] for m in messages)
    assert "45 + 32 = 77" in joined
    assert "INTERDIT" in joined


@requires_core
def test_calculation_failure_says_so_explicitly(core_with_history: LucasCore, monkeypatch) -> None:
    """Une expression qui échoue à s'évaluer (ex. division par zéro) doit le dire, pas se taire."""
    monkeypatch.setattr("modules.calculator.Calculator.calculate", lambda self, expr: None)
    messages = core_with_history._build_messages("combien font 10 / 0 ?", "local")
    joined = " ".join(m["content"] for m in messages)
    assert "N'A PAS PU ÊTRE ÉVALUÉE" in joined
    assert "10 / 0" in joined


@requires_core
def test_calculation_context_absent_when_question_unrelated(core_with_history: LucasCore) -> None:
    messages = core_with_history._build_messages("bonjour", "local")
    assert not any("CALCUL RÉEL" in m["content"] for m in messages)


# ── Recherche web (04/08/2026) ────────────────────────────────────────

class _FakeWebSearch:
    def __init__(self, log_event=None) -> None:
        self.log_event = log_event

    def get_summary(self, query: str, max_results: int = 3) -> str:
        return f"Résultats pour « {query} » :\n1. Exemple - http://exemple.test\n   Un extrait réel."


@requires_core
def test_cloud_never_receives_websearch_context(core_with_history: LucasCore, monkeypatch) -> None:
    monkeypatch.setattr("modules.web_search.WebSearch", _FakeWebSearch)
    messages = core_with_history._build_messages("cherche sur internet la météo", "cloud")
    assert not any("RECHERCHE WEB" in m["content"] for m in messages)


@requires_core
def test_local_receives_the_real_websearch_results(core_with_history: LucasCore, monkeypatch) -> None:
    monkeypatch.setattr("modules.web_search.WebSearch", _FakeWebSearch)
    messages = core_with_history._build_messages("cherche sur internet la météo", "local")
    joined = " ".join(m["content"] for m in messages)
    assert "Un extrait réel" in joined
    assert "INTERDIT" in joined


@requires_core
def test_websearch_context_absent_when_question_unrelated(core_with_history: LucasCore, monkeypatch) -> None:
    monkeypatch.setattr("modules.web_search.WebSearch", _FakeWebSearch)
    messages = core_with_history._build_messages("bonjour", "local")
    assert not any("RECHERCHE WEB" in m["content"] for m in messages)


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


# ── Reasoning Engine — désactivé par défaut (config.REASONING_ENGINE_ENABLED) ──

class _FakeReasoning:
    def plan(self, question: str, context: str = ""):
        from core.reasoning_engine import ReasoningResult

        return ReasoningResult(plan="- Un point à couvrir", used_reasoning=True)


@requires_core
def test_reasoning_disabled_by_default_adds_no_block(core_with_history: LucasCore, monkeypatch) -> None:
    monkeypatch.setattr(lucas_core, "ReasoningEngine", lambda: _FakeReasoning())
    messages = core_with_history._build_messages("compare ces stratégies", "local")
    assert not any("Points à couvrir" in m["content"] for m in messages)


@requires_core
def test_reasoning_enabled_adds_a_plan_block(core_with_history: LucasCore, monkeypatch) -> None:
    monkeypatch.setattr(lucas_core, "REASONING_ENGINE_ENABLED", True)
    monkeypatch.setattr(lucas_core, "ReasoningEngine", lambda: _FakeReasoning())
    messages = core_with_history._build_messages("compare ces stratégies", "local")
    assert any("Points à couvrir" in m["content"] for m in messages)


@requires_core
def test_reasoning_never_reaches_the_cloud(core_with_history: LucasCore, monkeypatch) -> None:
    """Même garde que le RAG et les événements : rien de plus vers le cloud."""
    monkeypatch.setattr(lucas_core, "REASONING_ENGINE_ENABLED", True)
    monkeypatch.setattr(lucas_core, "ReasoningEngine", lambda: _FakeReasoning())
    messages = core_with_history._build_messages("compare ces stratégies", "cloud")
    assert not any("Points à couvrir" in m["content"] for m in messages)


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
