# test_reasoning_engine.py — core/reasoning_engine.py (IDEAS.md #59, v1)

from __future__ import annotations

from core import reasoning_engine
from core.reasoning_engine import ReasoningEngine


def test_empty_question_short_circuits_without_calling_the_model(monkeypatch) -> None:
    def boom(messages):
        raise AssertionError("ask_local ne doit pas être appelé sur une question vide")

    monkeypatch.setattr(reasoning_engine, "ask_local", boom)

    result = ReasoningEngine().plan("   ")

    assert result.plan == ""
    assert result.used_reasoning is False


def test_simple_question_yields_no_plan(monkeypatch) -> None:
    monkeypatch.setattr(reasoning_engine, "ask_local", lambda messages: "AUCUN")

    result = ReasoningEngine().plan("Quelle heure est-il ?")

    assert result.plan == ""
    assert result.used_reasoning is False


def test_no_plan_marker_is_recognized_case_insensitively(monkeypatch) -> None:
    monkeypatch.setattr(reasoning_engine, "ask_local", lambda messages: "aucun.")

    result = ReasoningEngine().plan("Bonjour")

    assert result.used_reasoning is False


def test_complex_question_yields_a_plan(monkeypatch) -> None:
    plan_text = "- Vérifier le solde actuel\n- Comparer aux dépenses du mois"
    monkeypatch.setattr(reasoning_engine, "ask_local", lambda messages: plan_text)

    result = ReasoningEngine().plan("Est-ce que je peux me permettre cet achat ce mois-ci ?")

    assert result.plan == plan_text
    assert result.used_reasoning is True


def test_model_failure_degrades_without_a_plan(monkeypatch) -> None:
    monkeypatch.setattr(
        reasoning_engine, "ask_local", lambda messages: "[Erreur] Impossible de contacter Ollama"
    )

    result = ReasoningEngine().plan("Compare ces trois stratégies d'épargne")

    assert result.plan == ""
    assert result.used_reasoning is False


def test_plan_prompt_is_the_first_system_message(monkeypatch) -> None:
    captured = {}

    def fake(messages):
        captured["messages"] = messages
        return "AUCUN"

    monkeypatch.setattr(reasoning_engine, "ask_local", fake)

    ReasoningEngine().plan("Une question quelconque")

    assert captured["messages"][0]["role"] == "system"
    assert captured["messages"][0]["content"] == reasoning_engine.PLAN_PROMPT
    assert captured["messages"][-1] == {"role": "user", "content": "Une question quelconque"}


def test_context_is_included_when_given(monkeypatch) -> None:
    captured = {}

    def fake(messages):
        captured["messages"] = messages
        return "AUCUN"

    monkeypatch.setattr(reasoning_engine, "ask_local", fake)

    ReasoningEngine().plan("Et pour l'année suivante ?", context="Cyril : Quel est mon budget ?")

    contents = [m["content"] for m in captured["messages"]]
    assert any("Cyril : Quel est mon budget ?" in c for c in contents)


def test_no_context_means_no_extra_system_message(monkeypatch) -> None:
    captured = {}

    def fake(messages):
        captured["messages"] = messages
        return "AUCUN"

    monkeypatch.setattr(reasoning_engine, "ask_local", fake)

    ReasoningEngine().plan("Une question sans contexte")

    assert len(captured["messages"]) == 2
