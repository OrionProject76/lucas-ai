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
    load_directory,
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


# ── Mise en forme du modèle (ajouté le 05/08/2026, bascule gpt-oss:20b) ──
#
# Audit de ce que le changement de modèle pouvait casser silencieusement.
# La comparaison à la liste fermée se fait par ÉGALITÉ STRICTE : toute
# décoration autour du mot fait retomber sur UNCATEGORIZED.
#
# Mesuré sur le vrai modèle : 6 libellés sur 6 correctement catégorisés,
# avec une réponse nue — le prompt le contient bien. Ce n'était donc PAS
# un correctif d'urgence. Mais gpt-oss emploie volontiers le gras
# Markdown ailleurs dans ses réponses (« **Résoudre** au subjonctif… »),
# et `**Alimentation**` retombait bel et bien sur UNCATEGORIZED.


@pytest.mark.parametrize(
    "reponse, attendu",
    [
        ("**Alimentation**", "Alimentation"),   # gras Markdown
        ("_Transport_", "Transport"),           # italique
        ('"Loisirs"', "Loisirs"),               # guillemets
        ("Revenus.", "Revenus"),                # point final
        ("Logement ", "Logement"),         # espace fine insécable
        ("alimentation", "Alimentation"),       # casse
    ],
)
def test_formatting_around_the_category_is_ignored(reponse: str, attendu: str) -> None:
    assert categorize_by_llm("x", ask=lambda messages: reponse) == attendu


def test_a_category_buried_in_a_sentence_is_still_refused() -> None:
    """
    ⚠️ Choix DÉLIBÉRÉ, et différent de celui fait pour le classifieur
    d'intention (core/intent.py), qui repêche un label noyé dans une
    phrase.

    La différence est réelle : « Autre » et « Revenus » sont des mots
    courants, qu'une phrase explicative peut contenir sans les désigner.
    Un faux positif inventerait une catégorie sur une vraie transaction
    de Cyril — exactement ce que ce module refuse : « on préfère un trou
    visible à une catégorie inventée ».
    """
    assert categorize_by_llm("x", ask=lambda m: "La catégorie est Alimentation") == UNCATEGORIZED
    assert categorize_by_llm("x", ask=lambda m: "Sans doute Autre, mais je ne suis pas sûr") == UNCATEGORIZED


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
    LucasCore.ask() qui route et pourrait choisir le cloud. Un libellé
    bancaire ne sort pas de la machine (CLAUDE.md règle 3).
    """
    import inspect

    from core.local_llm import ask_local
    from modules import finance_categorizer

    source = inspect.getsource(finance_categorizer.categorize_by_llm)
    assert "ask_local" in source
    assert "LucasCore" not in source
    assert "ask_cloud" not in source
    assert callable(ask_local)


def test_categorize_by_llm_really_calls_ask_local_when_not_injected(monkeypatch) -> None:
    """
    La garde ci-dessus vérifie le texte du code ; celle-ci vérifie que la
    branche par défaut (aucun `ask` fourni) s'exécute réellement.
    """
    import core.local_llm as local_llm_module

    called = []

    def fake_ask_local(messages):
        called.append(messages)
        return "Transport"

    monkeypatch.setattr(local_llm_module, "ask_local", fake_ask_local)

    assert categorize_by_llm("libellé quelconque") == "Transport"
    assert len(called) == 1


def test_categorize_falls_back_to_the_llm_for_an_unrecognized_label() -> None:
    """
    test_rules_win_over_llm prouve l'inverse (un libellé reconnu
    n'atteint jamais le LLM) — celui-ci prouve qu'un libellé NON reconnu
    l'atteint bien, plutôt que de rester bloqué avant.
    """
    called = []

    def spy(messages):
        called.append(messages)
        return "Transport"

    assert categorize("XYZ VIREMENT DIVERS 9988", ask=spy) == "Transport"
    assert len(called) == 1


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


def test_unreadable_date_is_reported_clearly() -> None:
    """Trou de couverture fermé le 04/08/2026 : symétrique au montant illisible."""
    with pytest.raises(CSVFormatError, match="Format de date non reconnu"):
        _parse_date("le douze janvier")


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


def test_a_windows_1252_encoded_file_is_read_without_crashing(tmp_path) -> None:
    """
    Bug réel trouvé le 04/08/2026 sur un premier export réel de Cyril
    (voir ROADMAP.md §5.23) : encodage codé en dur en utf-8-sig, levait
    UnicodeDecodeError NON RATTRAPÉE (un crash, pas même un
    CSVFormatError propre) sur un export Windows-1252 — encodage courant
    des exports bancaires français plus anciens, aucun rapport avec une
    banque en particulier. Contenu ici entièrement fabriqué.
    """
    content = "date;libelle;montant\n02/01/2026;Café du Commerce;-4,50\n"
    path = tmp_path / "releve.csv"
    path.write_bytes(content.encode("cp1252"))

    manager = FinanceManager()
    added = manager.import_csv(path, use_llm=False)
    assert added == 1
    assert manager.transactions[0]["montant"] == pytest.approx(-4.50)


def test_date_transaction_is_a_recognized_date_column(tmp_path) -> None:
    """Alias ajouté le 04/08/2026, trouvé sur un second export réel — texte générique."""
    path = _write_csv(
        tmp_path, "date transaction;libelle;montant\n05/01/2026;Test;-10,00\n"
    )
    manager = FinanceManager()
    added = manager.import_csv(path, use_llm=False)
    assert added == 1


def test_a_header_with_more_columns_than_the_data_rows_still_works(tmp_path) -> None:
    """
    Structure réelle trouvée le 04/08/2026 (voir ROADMAP.md §5.23) : l'en-tête
    d'un second export a un champ vide en trop en fin de ligne (11 colonnes
    contre 10 dans chaque ligne de transaction) — zip() aligne sur le plus
    court, les colonnes utiles restant dans les premières positions.
    """
    path = _write_csv(
        tmp_path,
        "date transaction;libelle;montant;extra\n05/01/2026;Test;-10,00\n",
    )
    manager = FinanceManager()
    added = manager.import_csv(path, use_llm=False)
    assert added == 1
    assert manager.transactions[0]["montant"] == pytest.approx(-10.0)


def test_a_preamble_before_the_real_header_is_skipped(tmp_path) -> None:
    """
    Bug réel trouvé le 04/08/2026 (voir ROADMAP.md §5.23) : un export
    "comptable" réel fait précéder le tableau de transactions d'un
    résumé de compte (numéro, période, solde) sur une seule ligne, séparé
    du vrai en-tête par une ligne vide — la ligne 0 n'est donc pas
    toujours l'en-tête. Structure REPRODUITE ici (forme du préambule),
    aucun contenu réel de Cyril.
    """
    content = (
        'RESUME;01/01/2026;31/01/2026;2;31/01/2026;"1000,00 EUR"\n'
        "\n"
        "date;libelle;montant\n"
        "02/01/2026;Fournisseur Test;-50,00\n"
        "15/01/2026;Fournisseur Test Deux;-25,00\n"
    )
    path = _write_csv(tmp_path, content)

    manager = FinanceManager()
    added = manager.import_csv(path, use_llm=False)
    assert added == 2
    assert manager.transactions[0]["montant"] == pytest.approx(-50.0)
    assert manager.transactions[1]["montant"] == pytest.approx(-25.0)


def test_semicolon_is_tried_when_the_sniffer_cannot_decide(tmp_path) -> None:
    """
    Bug réel trouvé le 04/08/2026 (voir ROADMAP.md §5.23) : le préambule
    ci-dessus fait échouer csv.Sniffer() (formes de ligne trop
    différentes) — le repli fixe sur la virgule était une supposition
    fausse pour un fichier réellement délimité par des points-virgules.
    Corrigé : virgule PUIS point-virgule essayés avant d'abandonner.
    """
    content = (
        'RESUME;01/01/2026;31/01/2026;2;31/01/2026;"1000,00 EUR"\n'
        "\n"
        "date;libelle;montant de l'operation\n"
        "02/01/2026;Fournisseur Trois, Quatre;-12,34\n"
    )
    path = _write_csv(tmp_path, content)

    manager = FinanceManager()
    added = manager.import_csv(path, use_llm=False)
    assert added == 1
    assert manager.transactions[0]["montant"] == pytest.approx(-12.34)


def test_montant_de_l_operation_is_a_recognized_amount_column(tmp_path) -> None:
    """Alias ajouté le 04/08/2026, trouvé sur un export réel — texte générique, pas propre à une banque."""
    path = _write_csv(
        tmp_path, "date,libelle,montant de l'operation\n05/01/2026,Test,-10,00\n"
    )
    manager = FinanceManager()
    added = manager.import_csv(path, use_llm=False)
    assert added == 1


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


def test_a_single_column_file_falls_back_to_the_default_dialect(tmp_path) -> None:
    """
    Trou de couverture fermé le 04/08/2026 : sans délimiteur du tout,
    csv.Sniffer().sniff() lève csv.Error — repli sur csv.excel. Le fichier
    reste malgré tout invalide (une seule colonne), mais pour la bonne
    raison (colonne manquante), pas un crash sur le Sniffer.
    """
    path = _write_csv(tmp_path, "Date\n02/01/2026\n")
    manager = FinanceManager()
    with pytest.raises(CSVFormatError, match="libelle"):
        manager.import_csv(path, use_llm=False)


def test_a_trailing_blank_line_is_ignored(tmp_path) -> None:
    """Une ligne vide en fin de fichier ne doit pas devenir une transaction fantôme."""
    path = _write_csv(tmp_path, "date,libelle,montant\n2026-01-05,CARREFOUR,-84.30\n\n")
    manager = FinanceManager()
    added = manager.import_csv(path, use_llm=False)
    assert added == 1
    assert len(manager.transactions) == 1


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


def test_summary_gives_the_amount_of_uncategorized_transactions(tmp_path) -> None:
    """
    Régression du 03/08/2026 : sans le montant ici, qwen2.5:7b invente un
    chiffre plausible (447.10 EUR) pour la seule donnée manquante du
    résumé — vérifié en conditions réelles, vrai Ollama — malgré la
    consigne « n'invente jamais un montant » côté core/lucas_core.py. Le
    montant réel doit être présent, pas seulement date+libellé.
    """
    path = _write_csv(tmp_path, "date,libelle,montant\n2026-01-28,VIR SEPA GHRTX,-150.00\n")
    manager = FinanceManager()
    manager.import_csv(path, use_llm=False)

    assert "150.00 EUR" in manager.get_summary()


def test_summary_signals_truncation_beyond_five_uncategorized(tmp_path) -> None:
    """
    Même famille de bug que le test ci-dessus : l'en-tête annonce le
    NOMBRE total de transactions non catégorisées, mais seules 5 sont
    listées en détail. Sans marqueur explicite, ce serait un second trou
    silencieux — le modèle pourrait inventer les transactions restantes.
    """
    rows = "\n".join(
        f"2026-01-{i:02d},VIR SEPA {i},-{i}.00" for i in range(1, 8)
    )
    path = _write_csv(tmp_path, f"date,libelle,montant\n{rows}\n")
    manager = FinanceManager()
    manager.import_csv(path, use_llm=False)

    summary = manager.get_summary()
    assert "7 transaction(s) non catégorisée(s)" in summary
    assert "... et 2 autre(s), non détaillée(s) ici" in summary


def test_summary_without_transactions_does_not_crash() -> None:
    assert "Aucune transaction" in FinanceManager().get_summary()


def test_expenses_are_sorted_by_amount() -> None:
    manager = FinanceManager()
    manager.import_csv("data/sample_transactions.csv", use_llm=False)
    amounts = list(manager.get_expenses_by_category().values())
    assert amounts == sorted(amounts, reverse=True)


# ── load_directory() — contrepartie chat/API, 03/08/2026 ─────────────

def test_load_directory_returns_empty_manager_when_missing(tmp_path) -> None:
    """Un dossier absent ne doit jamais lever — get_summary() dira « aucune »."""
    manager, skipped = load_directory(tmp_path / "n_existe_pas")
    assert manager.transactions == []
    assert skipped == []


def test_load_directory_empty_folder(tmp_path) -> None:
    manager, skipped = load_directory(tmp_path)
    assert manager.transactions == []
    assert skipped == []


def test_load_directory_imports_every_csv(tmp_path) -> None:
    _write_csv(tmp_path, "date,libelle,montant\n2026-01-05,CARREFOUR,-10\n", "a.csv")
    _write_csv(tmp_path, "date,libelle,montant\n2026-01-06,EDF,-20\n", "b.csv")
    manager, skipped = load_directory(tmp_path)
    assert len(manager.transactions) == 2
    assert skipped == []


def test_load_directory_ignores_non_csv_files(tmp_path) -> None:
    _write_csv(tmp_path, "date,libelle,montant\n2026-01-05,CARREFOUR,-10\n", "a.csv")
    (tmp_path / "notes.txt").write_text("pas un relevé", encoding="utf-8")
    manager, skipped = load_directory(tmp_path)
    assert len(manager.transactions) == 1
    # `skipped` était dépaqueté puis jamais vérifié : le test prouvait que
    # le .txt n'entrait pas dans les transactions, pas ce qu'il devenait.
    # `skipped` liste les CSV ILLISIBLES — un .txt n'en est pas un, il ne
    # doit donc pas y figurer non plus.
    assert skipped == [], "un .txt n'est pas un relevé illisible, il ne doit pas y figurer"


def test_load_directory_reports_malformed_file_without_failing_the_others(tmp_path) -> None:
    """Un relevé mal formé n'empêche pas d'importer les autres — mais reste signalé."""
    _write_csv(tmp_path, "date,libelle,montant\n2026-01-05,CARREFOUR,-10\n", "bon.csv")
    _write_csv(tmp_path, "libelle,montant\nCARREFOUR,-10\n", "casse.csv")  # colonne date absente
    manager, skipped = load_directory(tmp_path)
    assert len(manager.transactions) == 1
    assert len(skipped) == 1
    assert "casse.csv" in skipped[0]


def test_load_directory_never_calls_the_llm_by_default(tmp_path) -> None:
    """
    use_llm=False par défaut : appelé à chaque tour de conversation
    (core/lucas_core.py), pas une fois à l'indexation comme le RAG.
    """
    _write_csv(
        tmp_path,
        "date,libelle,montant\n2026-01-28,VIR SEPA GHRTX,-150.00\n",
        "releve.csv",
    )
    manager, _ = load_directory(tmp_path)
    assert manager.transactions[0]["categorie"] == UNCATEGORIZED, (
        "sans mot-clé reconnu par les règles et sans LLM, la transaction "
        "doit rester visiblement non catégorisée"
    )


def test_load_directory_real_sample_file() -> None:
    """La contrepartie chat doit fonctionner sur le fichier d'exemple versionné."""
    import shutil
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy("data/sample_transactions.csv", Path(tmp) / "sample.csv")
        manager, skipped = load_directory(tmp)
        assert len(manager.transactions) == 15
        assert skipped == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
