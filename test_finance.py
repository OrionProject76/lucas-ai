# test_finance.py — import CSV, catégorisation et résumé financier
#
# ⚠️ Règle testée en priorité : aucun libellé bancaire ne doit pouvoir
# partir vers le cloud. La catégorisation LLM passe par ask_local, jamais
# par un routeur (CLAUDE.md règle 3, règle 4 : CSV uniquement).
#
# Aucun appel à Ollama : la fonction `ask` est injectée dans tous les tests.

from __future__ import annotations

import pytest

from modules.finance_categorizer import (
    CATEGORIES,
    UNCATEGORIZED,
    build_prompt,
    categorize,
    categorize_by_llm,
    categorize_by_rules,
)
from modules.finance_manager import (
    CSVFormatError,
    FinanceManager,
    _parse_amount,
    _parse_date,
)

# ── Catégorisation par règles ─────────────────────────────────────────

@pytest.mark.parametrize(
    "label, expected",
    [
        ("CARREFOUR MARKET", "Alimentation"),
        ("EDF facture electricite", "Logement"),
        ("Paiement de loyer", "Logement"),
        ("TOTAL ENERGIES carburant", "Transport"),
        ("Netflix abonnement", "Abonnements"),
        ("PHARMACIE DU CENTRE", "Santé"),
        ("Virement salaire", "Revenus"),
        ("Paiement d'électricité", "Logement"),
    ],
)
def test_rules_recognize_common_labels(label: str, expected: str) -> None:
    assert categorize_by_rules(label) == expected


def test_rules_ignore_case_and_accents() -> None:
    assert categorize_by_rules("ÉLECTRICITÉ ENGIE") == "Logement"
    assert categorize_by_rules("pharmacie") == categorize_by_rules("PHARMACIE")


def test_unknown_label_returns_none_not_a_default_category() -> None:
    """
    None et pas « Autre » : l'appelant doit pouvoir distinguer « rien
    trouvé » de « classé divers » pour décider s'il interroge le LLM.
    """
    assert categorize_by_rules("VIR SEPA GHRTX 4471") is None


# ── Catégorisation par LLM local ──────────────────────────────────────

def test_llm_answer_is_validated_against_the_closed_list() -> None:
    assert categorize_by_llm("VIR SEPA 4471", ask=lambda messages: "Transport") == "Transport"


def test_llm_hallucination_is_rejected() -> None:
    """Une catégorie inventée est refusée : un trou vaut mieux qu'un faux."""
    result = categorize_by_llm("VIR SEPA 4471", ask=lambda messages: "Cryptomonnaies")
    assert result == UNCATEGORIZED


def test_llm_verbose_answer_is_rejected() -> None:
    verbose = "Je pense qu'il s'agit de la catégorie Transport."
    assert categorize_by_llm("x", ask=lambda messages: verbose) == UNCATEGORIZED


def test_llm_failure_does_not_break_the_import() -> None:
    def broken(messages):
        raise ConnectionError("Ollama injoignable")

    assert categorize_by_llm("x", ask=broken) == UNCATEGORIZED


def test_prompt_constrains_the_model_to_the_category_list() -> None:
    prompt = build_prompt("CARREFOUR")
    system = prompt[0]["content"]
    assert all(category in system for category in CATEGORIES)
    assert "CARREFOUR" in prompt[1]["content"]


def test_rules_win_over_llm(monkeypatch) -> None:
    """Un libellé reconnu par les règles ne doit jamais atteindre le LLM."""
    called = []

    def spy(messages):
        called.append(messages)
        return "Autre"

    assert categorize("CARREFOUR MARKET", ask=spy) == "Alimentation"
    assert called == [], "aucun appel LLM pour un libellé déjà reconnu"


def test_use_llm_false_stays_offline() -> None:
    def must_not_be_called(messages):
        raise AssertionError("le LLM ne doit pas être appelé")

    assert categorize("VIR SEPA 4471", use_llm=False, ask=must_not_be_called) == UNCATEGORIZED


def test_default_llm_is_local_only() -> None:
    """
    Garde anti-régression sur la sécurité : par défaut, la catégorisation
    doit appeler core.local_llm.ask_local (Ollama sur localhost), jamais
    OrionCore.ask() qui route et pourrait choisir le cloud. Un libellé
    bancaire ne sort pas de la machine (CLAUDE.md règle 3).
    """
    import inspect

    from core.local_llm import ask_local
    from modules import finance_categorizer

    source = inspect.getsource(finance_categorizer.categorize_by_llm)
    assert "ask_local" in source
    assert "OrionCore" not in source
    assert "ask_cloud" not in source
    assert callable(ask_local)


# ── Analyse de format ─────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1234.56", 1234.56),
        ("1 234,56", 1234.56),
        ("-1234,56 €", -1234.56),
        ("1.234,56", 1234.56),
        ("", 0.0),
    ],
)
def test_amount_parsing_handles_french_formats(raw: str, expected: float) -> None:
    assert _parse_amount(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["2026-01-02", "02/01/2026", "02-01-2026", "02.01.2026"])
def test_date_parsing_handles_common_formats(raw: str) -> None:
    parsed = _parse_date(raw)
    assert (parsed.year, parsed.month, parsed.day) == (2026, 1, 2)


def test_unreadable_amount_is_reported_clearly() -> None:
    with pytest.raises(CSVFormatError, match="Montant illisible"):
        _parse_amount("douze euros")


# ── Import CSV ────────────────────────────────────────────────────────

def _write_csv(tmp_path, content: str, name: str = "releve.csv"):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_import_sample_file() -> None:
    """Le fichier d'exemple versionné doit rester importable."""
    manager = FinanceManager()
    count = manager.import_csv("data/sample_transactions.csv", use_llm=False)
    assert count == 15
    assert manager.get_income_total() == pytest.approx(4800.0)
    assert manager.get_expense_total() > 0


def test_category_column_is_optional(tmp_path) -> None:
    """Un export bancaire réel n'a pas de colonne catégorie."""
    path = _write_csv(tmp_path, "date,libelle,montant\n2026-01-05,CARREFOUR,-84.30\n")
    manager = FinanceManager()
    manager.import_csv(path, use_llm=False)
    assert manager.transactions[0]["categorie"] == "Alimentation"


def test_existing_category_is_respected(tmp_path) -> None:
    path = _write_csv(
        tmp_path,
        "date,libelle,montant,categorie\n2026-01-05,CARREFOUR,-84.30,Loisirs\n",
    )
    manager = FinanceManager()
    manager.import_csv(path, use_llm=False)
    assert manager.transactions[0]["categorie"] == "Loisirs", "ne pas écraser un choix explicite"


def test_debit_credit_columns_are_converted_to_signed_amounts(tmp_path) -> None:
    path = _write_csv(
        tmp_path,
        "Date;Libellé;Débit;Crédit\n"
        "02/01/2026;Virement salaire;;2400,00\n"
        "03/01/2026;Loyer;1000,00;\n",
    )
    manager = FinanceManager()
    manager.import_csv(path, use_llm=False)
    assert manager.transactions[0]["montant"] == pytest.approx(2400.0)
    assert manager.transactions[1]["montant"] == pytest.approx(-1000.0)


def test_semicolon_and_accented_headers_are_supported(tmp_path) -> None:
    path = _write_csv(
        tmp_path,
        "Date opération;Libellé;Montant\n05/01/2026;CARREFOUR;-84,30\n",
    )
    manager = FinanceManager()
    manager.import_csv(path, use_llm=False)
    assert manager.transactions[0]["libelle"] == "CARREFOUR"


def test_missing_required_column_is_reported(tmp_path) -> None:
    path = _write_csv(tmp_path, "libelle,montant\nCARREFOUR,-84.30\n")
    manager = FinanceManager()
    with pytest.raises(CSVFormatError, match="date"):
        manager.import_csv(path, use_llm=False)


def test_missing_amount_column_is_reported(tmp_path) -> None:
    path = _write_csv(tmp_path, "date,libelle\n2026-01-05,CARREFOUR\n")
    manager = FinanceManager()
    with pytest.raises(CSVFormatError, match="montant"):
        manager.import_csv(path, use_llm=False)


def test_missing_file_is_reported() -> None:
    manager = FinanceManager()
    with pytest.raises(CSVFormatError, match="introuvable"):
        manager.import_csv("data/n_existe_pas.csv")


def test_importing_twice_accumulates(tmp_path) -> None:
    path = _write_csv(tmp_path, "date,libelle,montant\n2026-01-05,CARREFOUR,-10\n")
    manager = FinanceManager()
    manager.import_csv(path, use_llm=False)
    manager.import_csv(path, use_llm=False)
    assert len(manager.transactions) == 2


# ── Résumé ────────────────────────────────────────────────────────────

def test_summary_reports_uncategorized_transactions(tmp_path) -> None:
    """Un trou doit rester visible dans le résumé, pas être masqué."""
    path = _write_csv(tmp_path, "date,libelle,montant\n2026-01-28,VIR SEPA GHRTX,-150.00\n")
    manager = FinanceManager()
    manager.import_csv(path, use_llm=False)

    summary = manager.get_summary()
    assert "non catégorisée" in summary
    assert "VIR SEPA GHRTX" in summary


def test_summary_without_transactions_does_not_crash() -> None:
    assert "Aucune transaction" in FinanceManager().get_summary()


def test_expenses_are_sorted_by_amount() -> None:
    manager = FinanceManager()
    manager.import_csv("data/sample_transactions.csv", use_llm=False)
    amounts = list(manager.get_expenses_by_category().values())
    assert amounts == sorted(amounts, reverse=True)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
