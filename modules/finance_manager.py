# modules/finance_manager.py — import et analyse de relevés bancaires CSV
#
# CSV uniquement, jamais de connexion bancaire directe (CLAUDE.md règle 4).
#
# ⚠️ Les données manipulées ici sont ultra-sensibles. Elles ne quittent
# jamais la machine : la catégorisation LLM passe par Ollama en local
# (voir modules/finance_categorizer.py). Les relevés réels vivent dans
# data/finance/, ignoré par git.
#
# Convention de signe : montant NÉGATIF = dépense, POSITIF = revenu.
# Les exports au format débit/crédit séparés sont convertis à l'import.

import csv
from datetime import datetime
from pathlib import Path

from modules.finance_categorizer import UNCATEGORIZED, categorize

# Noms de colonnes rencontrés dans les exports bancaires français.
# Comparés en minuscules, sans accents ni espaces superflus.
COLUMN_ALIASES: dict[str, list[str]] = {
    "date": ["date", "date operation", "date de l'operation", "date valeur"],
    "libelle": ["libelle", "libelle operation", "label", "description",
                "nature", "intitule", "motif"],
    "montant": ["montant", "amount", "somme", "valeur"],
    "debit": ["debit", "retrait", "sortie"],
    "credit": ["credit", "depot", "entree"],
    "categorie": ["categorie", "category", "type"],
}

DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"]


class CSVFormatError(Exception):
    """Le fichier ne ressemble pas à un relevé exploitable."""


# Dossier des VRAIS relevés de Cyril — ignoré par git (voir .gitignore),
# jamais celui du dépôt (data/sample_transactions.csv, données fictives,
# suivi par git pour les tests).
DEFAULT_FINANCE_DIR = Path("data/finance")


def _normalize_header(name: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFD", name.strip().lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def _map_columns(fieldnames: list[str]) -> dict[str, str]:
    """Associe nos noms canoniques aux colonnes réelles du fichier."""
    mapping: dict[str, str] = {}
    for actual in fieldnames or []:
        normalized = _normalize_header(actual)
        for canonical, aliases in COLUMN_ALIASES.items():
            if normalized in aliases and canonical not in mapping:
                mapping[canonical] = actual
    return mapping


def _parse_date(raw: str) -> datetime:
    raw = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            # Date naïve assumée : une date de relevé bancaire n'a pas de
            # fuseau, lui en attribuer un fausserait les comparaisons.
            return datetime.strptime(raw, fmt)  # noqa: DTZ007
        except ValueError:
            continue
    raise CSVFormatError(f"Format de date non reconnu : « {raw} »")


def _parse_amount(raw: str) -> float:
    """
    Tolère « 1 234,56 », « 1234.56 », « -1234,56 € », « 1.234,56 ».
    Les exports bancaires français utilisent la virgule décimale et
    l'espace comme séparateur de milliers.
    """
    cleaned = raw.strip().replace("€", "").replace("EUR", "")
    cleaned = cleaned.replace(" ", "").replace(" ", "")
    if "," in cleaned:
        # virgule décimale : le point ne peut être qu'un séparateur de milliers
        cleaned = cleaned.replace(".", "").replace(",", ".")
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError as exc:
        raise CSVFormatError(f"Montant illisible : « {raw} »") from exc


class FinanceManager:
    """Charge un ou plusieurs relevés CSV et en tire un résumé."""

    def __init__(self) -> None:
        self.transactions: list[dict] = []

    # ── Import ────────────────────────────────────────────────────────

    def import_csv(
        self,
        filepath: str | Path,
        use_llm: bool = True,
        ask=None,
    ) -> int:
        """
        Importe un relevé et retourne le nombre de transactions ajoutées.

        La colonne `categorie` est facultative : absente ou vide, la
        catégorie est déduite (règles, puis LLM local si `use_llm`).
        Les transactions déjà chargées sont conservées — on peut cumuler
        plusieurs relevés.
        """
        path = Path(filepath)
        if not path.is_file():
            raise CSVFormatError(f"Fichier introuvable : {path}")

        with path.open(newline="", encoding="utf-8-sig") as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel  # défaut raisonnable : virgule

            reader = csv.DictReader(f, dialect=dialect)
            columns = _map_columns(reader.fieldnames)

            missing = [c for c in ("date", "libelle") if c not in columns]
            if missing:
                raise CSVFormatError(
                    f"Colonnes obligatoires absentes : {', '.join(missing)}. "
                    f"Colonnes trouvées : {reader.fieldnames}"
                )
            if "montant" not in columns and not {"debit", "credit"} & columns.keys():
                raise CSVFormatError(
                    "Aucune colonne de montant (ni « montant », ni « débit »/« crédit »)."
                )

            added = 0
            for row in reader:
                transaction = self._parse_row(row, columns, use_llm, ask)
                if transaction is not None:
                    self.transactions.append(transaction)
                    added += 1

        return added

    def _parse_row(self, row: dict, columns: dict, use_llm: bool, ask) -> dict | None:
        """Convertit une ligne. Retourne None pour une ligne vide (fin de fichier)."""
        raw_date = (row.get(columns["date"]) or "").strip()
        label = (row.get(columns["libelle"]) or "").strip()
        if not raw_date and not label:
            return None

        amount = self._extract_amount(row, columns)

        category = ""
        if "categorie" in columns:
            category = (row.get(columns["categorie"]) or "").strip()
        if not category:
            category = categorize(label, use_llm=use_llm, ask=ask)

        return {
            "date": _parse_date(raw_date),
            "libelle": label,
            "montant": amount,
            "categorie": category,
        }

    @staticmethod
    def _extract_amount(row: dict, columns: dict) -> float:
        """Montant signé, quel que soit le format d'origine."""
        if "montant" in columns:
            return _parse_amount(row.get(columns["montant"]) or "0")

        debit = _parse_amount(row.get(columns.get("debit", ""), "") or "0")
        credit = _parse_amount(row.get(columns.get("credit", ""), "") or "0")
        # Colonnes séparées : le débit est une dépense, donc négatif.
        return credit - abs(debit)

    # ── Analyse ───────────────────────────────────────────────────────

    def get_balance(self) -> float:
        return sum(t["montant"] for t in self.transactions)

    def get_expenses_by_category(self) -> dict[str, float]:
        """Dépenses (montants négatifs) agrégées par catégorie, en positif."""
        totals: dict[str, float] = {}
        for t in self.transactions:
            if t["montant"] < 0:
                totals[t["categorie"]] = totals.get(t["categorie"], 0) + abs(t["montant"])
        return dict(sorted(totals.items(), key=lambda kv: kv[1], reverse=True))

    def get_income_total(self) -> float:
        return sum(t["montant"] for t in self.transactions if t["montant"] > 0)

    def get_expense_total(self) -> float:
        """Total des dépenses, en valeur positive."""
        return abs(sum(t["montant"] for t in self.transactions if t["montant"] < 0))

    def get_uncategorized(self) -> list[dict]:
        """
        Transactions que ni les règles ni le LLM n'ont su classer.
        Exposées volontairement : un trou visible vaut mieux qu'une
        catégorie inventée qui fausserait le résumé.
        """
        return [t for t in self.transactions if t["categorie"] == UNCATEGORIZED]

    def get_summary(self) -> str:
        """Résumé texte, prêt à afficher dans le chat ou à lire à voix haute."""
        if not self.transactions:
            return "=== Résumé Financier ===\nAucune transaction importée."

        expenses = self.get_expenses_by_category()
        income = self.get_income_total()
        spent = self.get_expense_total()

        start = min(t["date"] for t in self.transactions).strftime("%d/%m/%Y")
        end = max(t["date"] for t in self.transactions).strftime("%d/%m/%Y")

        lines = [
            "=== Résumé Financier ===",
            f"Période : du {start} au {end} ({len(self.transactions)} transactions)",
            f"Solde total : {self.get_balance():.2f} EUR",
            f"Revenus : {income:.2f} EUR",
            f"Dépenses : {spent:.2f} EUR",
        ]

        if expenses:
            lines.append("")
            lines.append("Dépenses par catégorie :")
            for category, amount in expenses.items():
                share = amount / spent * 100 if spent else 0
                lines.append(f"  - {category} : {amount:.2f} EUR ({share:.0f} %)")

        uncategorized = self.get_uncategorized()
        if uncategorized:
            lines.append("")
            lines.append(f"⚠️ {len(uncategorized)} transaction(s) non catégorisée(s) :")
            for t in uncategorized[:5]:
                # ⚠️ Le montant doit être ici, pas seulement date+libellé.
                # Trouvé en validation réelle (03/08/2026, vrai Ollama) : sans
                # lui, qwen2.5:7b invente un chiffre plausible pour la seule
                # information manquante du résumé — malgré une consigne
                # explicite « n'invente jamais un montant » dans le bloc
                # injecté par core/lucas_core.py. Un trou dans les données
                # fournies au modèle reste un trou à deviner, quelle que
                # soit la consigne ; la seule protection fiable est de ne
                # rien laisser à deviner.
                lines.append(
                    f"  - {t['date'].strftime('%d/%m/%Y')} {t['libelle']} : "
                    f"{t['montant']:.2f} EUR"
                )

        return "\n".join(lines)


def load_directory(
    directory: str | Path = DEFAULT_FINANCE_DIR,
    use_llm: bool = False,
) -> tuple[FinanceManager, list[str]]:
    """
    Importe tous les relevés CSV d'un dossier dans un seul FinanceManager.

    ⚠️ `use_llm=False` par défaut, à l'inverse de `import_csv()` : ce
    chemin est appelé à CHAQUE question financière du chat (voir
    core/lucas_core.py), pas une fois pour toutes comme l'indexation RAG.
    Appeler le LLM local pour chaque libellé non reconnu à chaque tour de
    conversation ajouterait une latence imprévisible. Les règles
    déterministes (finance_categorizer.KEYWORD_RULES) suffisent pour
    l'essentiel ; ce qui reste « Non catégorisé » reste visible dans le
    résumé plutôt que d'être deviné ou de ralentir la réponse.

    Retourne un FinanceManager VIDE (pas une erreur) si le dossier
    n'existe pas ou ne contient aucun CSV — get_summary() dit alors
    explicitement qu'aucune transaction n'est importée. Un relevé mal
    formé est écarté SANS faire échouer les autres, mais signalé dans la
    liste retournée — un trou silencieux serait aussi trompeur qu'une
    catégorie inventée (même principe que get_uncategorized()).
    """
    manager = FinanceManager()
    path = Path(directory)
    skipped: list[str] = []
    if not path.is_dir():
        return manager, skipped

    for csv_path in sorted(path.glob("*.csv")):
        try:
            manager.import_csv(csv_path, use_llm=use_llm)
        except CSVFormatError as exc:
            skipped.append(f"{csv_path.name} ({exc})")

    return manager, skipped
