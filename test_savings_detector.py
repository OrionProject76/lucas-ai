# test_savings_detector.py — Détecteur d'économies (Workspace B-2)
#
# Données 100% synthétiques et fictives — jamais un relevé réel de Cyril,
# même en test (CLAUDE.md, "jamais afficher le contenu réel d'un fichier
# de données personnelles"). Les libellés/montants ci-dessous n'existent
# nulle part sur le disque.

from __future__ import annotations

from datetime import datetime

from modules import savings_detector


def _txn(date: str, libelle: str, montant: float, categorie: str = "Autre") -> dict:
    return {
        # Date naïve délibérée, même convention que modules/finance_manager.py
        # (_parse_date) : un relevé bancaire n'a pas de fuseau.
        "date": datetime.strptime(date, "%Y-%m-%d"),  # noqa: DTZ007
        "libelle": libelle,
        "montant": montant,
        "categorie": categorie,
    }


# ── detect_recurring_charges ────────────────────────────────────────


def test_detects_a_monthly_subscription_over_three_months() -> None:
    transactions = [
        _txn("2026-01-08", "NETFLIX.COM 08/01", -13.49, "Abonnements"),
        _txn("2026-02-08", "NETFLIX.COM 08/02", -13.49, "Abonnements"),
        _txn("2026-03-09", "NETFLIX.COM 09/03", -13.49, "Abonnements"),
    ]
    results = savings_detector.detect_recurring_charges(transactions)
    assert len(results) == 1
    assert results[0]["status"] == "detecte"
    assert results[0]["interval"] == "mensuel"
    assert results[0]["average_amount"] == -13.49
    assert len(results[0]["occurrences"]) == 3


def test_detects_an_annual_charge_with_only_two_occurrences() -> None:
    transactions = [
        _txn("2025-06-01", "ASSURANCE HABITATION", -180.0, "Logement"),
        _txn("2026-06-03", "ASSURANCE HABITATION", -180.0, "Logement"),
    ]
    results = savings_detector.detect_recurring_charges(transactions)
    assert len(results) == 1
    assert results[0]["interval"] == "annuel"


def test_two_monthly_occurrences_alone_are_not_enough_evidence() -> None:
    """Deux points espacés d'un mois ne suffisent pas — "sur plusieurs mois" (brief §3.1)."""
    transactions = [
        _txn("2026-01-08", "SALLE DE SPORT", -29.90, "Loisirs"),
        _txn("2026-02-08", "SALLE DE SPORT", -29.90, "Loisirs"),
    ]
    assert savings_detector.detect_recurring_charges(transactions) == []


def test_unrelated_single_transactions_are_not_recurring() -> None:
    transactions = [
        _txn("2026-01-05", "CARREFOUR MARKET", -45.20, "Alimentation"),
        _txn("2026-02-12", "PHARMACIE DU CENTRE", -12.30, "Santé"),
    ]
    assert savings_detector.detect_recurring_charges(transactions) == []


def test_income_is_never_treated_as_a_recurring_charge() -> None:
    """Un salaire mensuel identique n'est pas une "charge" — montant positif exclu."""
    transactions = [
        _txn("2026-01-01", "VIREMENT SALAIRE", 2400.0, "Revenus"),
        _txn("2026-02-01", "VIREMENT SALAIRE", 2400.0, "Revenus"),
        _txn("2026-03-01", "VIREMENT SALAIRE", 2400.0, "Revenus"),
    ]
    assert savings_detector.detect_recurring_charges(transactions) == []


def test_wildly_different_amounts_under_the_same_generic_label_do_not_group() -> None:
    """Deux enseignes différentes du même nom de chaîne ne doivent pas se mélanger."""
    transactions = [
        _txn("2026-01-05", "CARREFOUR PARIS 15", -40.0, "Alimentation"),
        _txn("2026-02-05", "CARREFOUR PARIS 15", -3000.0, "Alimentation"),
        _txn("2026-03-05", "CARREFOUR PARIS 15", -45.0, "Alimentation"),
    ]
    assert savings_detector.detect_recurring_charges(transactions) == []


def test_cash_withdrawals_at_the_same_atm_are_never_recurring_charges() -> None:
    """
    Régression réelle (09/08/2026) : des retraits DAB au même distributeur
    partagent le même libellé une fois les chiffres retirés (date, heure,
    référence, ET montant) — sans exclusion, ils se groupent comme une
    charge récurrente dont le "tarif" varie à chaque retrait.
    """
    transactions = [
        _txn("2026-03-04", "CARTE X3422 RETRAIT DAB 05/03 19H01 BRED SOTTEVILLE LES RO 00013732", -80.0, "Retraits"),
        _txn("2026-03-12", "CARTE X3422 RETRAIT DAB 17/03 20H41 BRED SOTTEVILLE LES RO 00013732", -180.0, "Retraits"),
        _txn("2026-04-10", "CARTE X3422 RETRAIT DAB 12/04 09H10 BRED SOTTEVILLE LES RO 00013732", -50.0, "Retraits"),
    ]
    assert savings_detector.detect_recurring_charges(transactions) == []
    assert savings_detector.detect_price_increases(transactions) == []
    assert savings_detector.detect_duplicate_charges(transactions) == []


def test_a_too_generic_short_label_is_never_grouped() -> None:
    transactions = [
        _txn("2026-01-05", "CB 4471", -10.0),
        _txn("2026-02-05", "CB 8832", -10.0),
        _txn("2026-03-05", "CB 1290", -10.0),
    ]
    assert savings_detector.detect_recurring_charges(transactions) == []


# ── detect_price_increases ──────────────────────────────────────────


def test_detects_a_silent_price_hike_on_a_recurring_charge() -> None:
    transactions = [
        _txn("2026-01-08", "SPOTIFY", -9.99, "Abonnements"),
        _txn("2026-02-08", "SPOTIFY", -9.99, "Abonnements"),
        _txn("2026-03-08", "SPOTIFY", -12.99, "Abonnements"),
    ]
    results = savings_detector.detect_price_increases(transactions)
    assert len(results) == 1
    hike = results[0]
    assert hike["previous_amount"] == -9.99
    assert hike["new_amount"] == -12.99
    assert hike["increase_pct"] == 30.0


def test_a_tiny_rounding_difference_is_not_a_price_increase() -> None:
    transactions = [
        _txn("2026-01-08", "SPOTIFY", -9.99, "Abonnements"),
        _txn("2026-02-08", "SPOTIFY", -9.99, "Abonnements"),
        _txn("2026-03-08", "SPOTIFY", -10.05, "Abonnements"),
    ]
    assert savings_detector.detect_price_increases(transactions) == []


def test_a_price_decrease_is_not_reported_as_an_increase() -> None:
    transactions = [
        _txn("2026-01-08", "SPOTIFY", -12.99, "Abonnements"),
        _txn("2026-02-08", "SPOTIFY", -12.99, "Abonnements"),
        _txn("2026-03-08", "SPOTIFY", -9.99, "Abonnements"),
    ]
    assert savings_detector.detect_price_increases(transactions) == []


# ── detect_duplicate_charges ─────────────────────────────────────────


def test_detects_a_probable_duplicate_and_marks_it_to_verify() -> None:
    transactions = [
        _txn("2026-01-10", "ABONNEMENT SALLE", -29.90, "Loisirs"),
        _txn("2026-01-11", "ABONNEMENT SALLE", -29.90, "Loisirs"),
    ]
    results = savings_detector.detect_duplicate_charges(transactions)
    assert len(results) == 1
    assert results[0]["status"] == "a_verifier"
    assert results[0]["gap_days"] == 1


def test_a_normal_monthly_recurrence_is_not_flagged_as_a_duplicate() -> None:
    transactions = [
        _txn("2026-01-08", "NETFLIX.COM", -13.49, "Abonnements"),
        _txn("2026-02-08", "NETFLIX.COM", -13.49, "Abonnements"),
    ]
    assert savings_detector.detect_duplicate_charges(transactions) == []


def test_close_dates_with_different_amounts_are_not_a_duplicate() -> None:
    transactions = [
        _txn("2026-01-10", "CARREFOUR MARKET", -45.20, "Alimentation"),
        _txn("2026-01-11", "CARREFOUR MARKET", -12.30, "Alimentation"),
    ]
    assert savings_detector.detect_duplicate_charges(transactions) == []


def test_never_returns_a_duplicate_with_a_certain_status() -> None:
    """
    Garde-fou explicite du brief (§5, RT-2) : quel que soit le jeu de
    données, aucun doublon ne doit jamais sortir d'ici avec un statut
    autre que "a_verifier".
    """
    transactions = [
        _txn("2026-01-10", "ABONNEMENT SALLE", -29.90, "Loisirs"),
        _txn("2026-01-10", "ABONNEMENT SALLE", -29.90, "Loisirs"),
        _txn("2026-01-12", "AUTRE CHARGE", -50.0, "Autre"),
        _txn("2026-01-13", "AUTRE CHARGE", -50.0, "Autre"),
    ]
    results = savings_detector.detect_duplicate_charges(transactions)
    assert len(results) == 2
    assert all(r["status"] == "a_verifier" for r in results)


# ── analyze() ─────────────────────────────────────────────────────────


def test_analyze_assembles_all_three_sections() -> None:
    transactions = [
        _txn("2026-01-08", "NETFLIX.COM", -13.49, "Abonnements"),
        _txn("2026-02-08", "NETFLIX.COM", -13.49, "Abonnements"),
        _txn("2026-03-08", "NETFLIX.COM", -13.49, "Abonnements"),
        _txn("2026-01-10", "ABONNEMENT SALLE", -29.90, "Loisirs"),
        _txn("2026-01-11", "ABONNEMENT SALLE", -29.90, "Loisirs"),
    ]
    result = savings_detector.analyze(transactions)
    assert set(result.keys()) == {"recurring_charges", "price_increases", "duplicates"}
    assert len(result["recurring_charges"]) == 1
    assert len(result["duplicates"]) == 1


def test_analyze_on_empty_transactions_returns_empty_sections() -> None:
    assert savings_detector.analyze([]) == {
        "recurring_charges": [], "price_increases": [], "duplicates": [],
    }
