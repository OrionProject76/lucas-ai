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
import io
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from modules.finance_categorizer import UNCATEGORIZED, categorize

# Nombre de lignes explorées avant de renoncer à trouver un en-tête
# exploitable — un export réel peut faire précéder le tableau de
# transactions d'un résumé de compte (numéro, période, solde), mais ce
# préambule ne s'étend jamais sur des centaines de lignes. Une valeur
# raisonnable évite de scanner un fichier entier qui n'a de toute façon
# aucun en-tête reconnaissable (voir ROADMAP.md §5.22, format à une
# seule colonne par ligne).
HEADER_SCAN_LIMIT = 20

# Noms de colonnes rencontrés dans les exports bancaires français.
# Comparés en minuscules, sans accents ni espaces superflus.
COLUMN_ALIASES: dict[str, list[str]] = {
    "date": ["date", "date operation", "date de l'operation", "date valeur"],
    "libelle": ["libelle", "libelle operation", "label", "description",
                "nature", "intitule", "motif"],
    "montant": ["montant", "amount", "somme", "valeur", "montant de l'operation"],
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


def _read_csv_text(path: Path) -> str:
    """
    Lit le fichier en texte, avec repli d'encodage.

    ⚠️ Bug réel trouvé le 04/08/2026 (premier export réel exploitable
    déposé par Cyril, format "export comptable" — voir ROADMAP.md §5.23) :
    `utf-8-sig` codé en dur levait `UnicodeDecodeError` (non rattrapée,
    donc un crash, pas même un `CSVFormatError` propre) sur un export
    encodé en Windows-1252 — encodage courant des exports bancaires
    français plus anciens, aucun rapport avec une banque en particulier.
    """
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def _normalize_header(name: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFD", name.strip().lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def _map_columns(fieldnames: Sequence[str] | None) -> dict[str, str]:
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

        text = _read_csv_text(path)
        sample = text[:4096]
        try:
            sniffed = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
        except csv.Error:
            sniffed = None

        # ⚠️ Deuxième bug réel trouvé le même jour, sur le même export
        # (voir ROADMAP.md §5.23) : quand le Sniffer échoue, le repli fixe
        # sur la virgule était une supposition, pas une déduction — ce
        # fichier est en réalité délimité par des points-virgules. Le
        # Sniffer échoue précisément parce que le résumé de compte qui
        # précède le tableau n'a pas la même forme que les lignes de
        # transaction ; une fois qu'on écarte cette hypothèse, essayer
        # virgule PUIS point-virgule (les deux délimiteurs déjà couverts
        # par test_finance.py sur des formats qui, eux, se laissent
        # deviner par le Sniffer) reste une déduction bornée, pas un
        # essai au hasard.
        candidates = [d for d in (sniffed, ",", ";") if d]
        seen: set[str] = set()
        delimiters_to_try = [d for d in candidates if not (d in seen or seen.add(d))]

        header_row: list[str] | None = None
        columns: dict[str, str] = {}
        first_candidate: list[str] | None = None
        chosen_delimiter = delimiters_to_try[0]
        # Nombre de lignes NON VIDES à sauter avant la première ligne de
        # transaction — position, pas contenu, pour ne jamais reconfondre
        # l'en-tête avec une ligne de donnée qui lui ressemblerait plus
        # loin dans un export multi-pages (en-têtes répétés par page).
        rows_before_data = 0

        for delimiter in delimiters_to_try:
            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            local_first: list[str] | None = None
            non_empty_seen = 0
            for candidate in reader:
                if not candidate:
                    continue
                non_empty_seen += 1
                if local_first is None:
                    local_first = candidate
                mapped = _map_columns(candidate)
                missing = [c for c in ("date", "libelle") if c not in mapped]
                has_amount = "montant" in mapped or bool({"debit", "credit"} & mapped.keys())
                if not missing and has_amount:
                    header_row, columns, chosen_delimiter = candidate, mapped, delimiter
                    rows_before_data = non_empty_seen
                    break
                if non_empty_seen >= HEADER_SCAN_LIMIT:
                    break
            if first_candidate is None:
                first_candidate = local_first
            if header_row is not None:
                break

        if header_row is None:
            mapped = _map_columns(first_candidate)
            missing = [c for c in ("date", "libelle") if c not in mapped]
            if missing:
                raise CSVFormatError(
                    f"Colonnes obligatoires absentes : {', '.join(missing)}. "
                    f"Colonnes trouvées : {first_candidate}"
                )
            raise CSVFormatError(
                "Aucune colonne de montant (ni « montant », ni « débit »/« crédit »)."
            )

        reader = csv.reader(io.StringIO(text), delimiter=chosen_delimiter)
        added = 0
        non_empty_seen = 0
        for row_values in reader:
            if not row_values:
                continue
            non_empty_seen += 1
            if non_empty_seen <= rows_before_data:
                continue
            row = dict(zip(header_row, row_values))
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
            reste = len(uncategorized) - 5
            if reste > 0:
                # ⚠️ Même famille de bug que le montant manquant ci-dessus :
                # sans ce marqueur, l'en-tête annonce N transactions mais
                # seules 5 sont listées — un trou silencieux que le modèle
                # pourrait combler en inventant les suivantes. Le marqueur
                # dit explicitement que la liste est coupée, pas complète.
                lines.append(f"  - ... et {reste} autre(s), non détaillée(s) ici")

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
