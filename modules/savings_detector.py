# modules/savings_detector.py — détecteur d'économies (Workspace B-2)
#
# Brief : cowork_workspace/BRIEF_DETECTEUR_ECONOMIES_B2_1.md. Analyse les
# transactions déjà importées par modules/finance_manager.py (aucune
# nouvelle donnée, aucune connexion réseau) pour repérer trois motifs
# mécaniques :
#   1. charges récurrentes (même marchand, montant proche, intervalle
#      régulier sur plusieurs mois)
#   2. hausses de tarif sur une charge récurrente déjà identifiée
#   3. doublons probables (deux charges quasi identiques à quelques jours
#      d'écart) — TOUJOURS restitués "à vérifier" (RT-3bis/RT-2,
#      CLAUDE.md/VISION_LONG_TERME.md) : jamais affirmés comme certains,
#      une ressemblance n'est pas une preuve.
#
# RT-3 : 100 % local, aucun appel LLM ni réseau — uniquement de
# l'agrégation déterministe sur des dicts déjà en mémoire. Comparaison
# fournisseurs (hors périmètre §4 du brief) nécessiterait une recherche
# web ; ce module ne la fait pas.

from __future__ import annotations

import itertools
import re
import statistics
from collections import defaultdict
from typing import TypedDict

from core.text_utils import normalize

# Longueur minimale d'une clé de regroupement — que ce soit _core_label()
# (chiffres retirés, récurrence/hausses) ou _duplicate_key() (libellé
# complet, doublons). Sous ce seuil, une clé du type "cb" est trop
# générique pour grouper sans faux positif — regroupe systématiquement
# des marchands sans rapport.
MIN_CORE_LABEL_LEN = 3

# Un mois réel varie de 28 à 31 jours ; une année de facturation peut
# glisser de quelques jours (jour ouvré, week-end). Fenêtres généreuses
# pour ne pas rater un prélèvement réel, resserrées assez pour ne pas
# confondre mensuel et bimensuel/annuel.
MONTHLY_GAP_DAYS = (25, 35)
ANNUAL_GAP_DAYS = (350, 380)

# Une charge "récurrente" doit rester dans le même ordre de grandeur à
# chaque occurrence — sans ce garde-fou, un libellé générique partagé par
# deux marchands sans rapport (ex. deux enseignes "CARREFOUR ...")
# grouperait des montants qui n'ont rien à voir.
AMOUNT_SANITY_MIN_RATIO = 0.3
AMOUNT_SANITY_MAX_RATIO = 3.0

# Une hausse de tarif doit être significative pour être signalée — pas un
# centime d'arrondi entre deux imports, ni une variation de quelques
# centimes qui n'a rien d'une décision tarifaire.
PRICE_INCREASE_MIN_RATIO = 0.05  # 5 %
PRICE_INCREASE_MIN_ABSOLUTE = 1.0  # EUR

# Un doublon probable : même marchand, montant quasi identique, à
# quelques jours d'écart au plus — un prélèvement mensuel normal n'entre
# jamais dans cette fenêtre (voir MONTHLY_GAP_DAYS ci-dessus), donc aucun
# recouvrement avec la détection de récurrence.
DUPLICATE_MAX_GAP_DAYS = 3
DUPLICATE_AMOUNT_TOLERANCE = 0.01  # EUR


class Transaction(TypedDict):
    date: object  # datetime — typé object ici pour éviter une dépendance croisée inutile
    libelle: str
    montant: float
    categorie: str


def _core_label(libelle: str) -> str:
    """
    Signature de regroupement : normalize() (minuscules, sans accents —
    core/text_utils.py) puis chiffres retirés (numéros de référence, dates
    dans le libellé) et espaces multiples réduits.

    "NETFLIX.COM 08/01" et "NETFLIX.COM 12/02" partagent la même
    signature ; "CARREFOUR PARIS 15" et "CARREFOUR LYON 3" restent
    distincts (le nom de ville n'est pas un chiffre) — intentionnel : ce
    module signale un PATRON mécanique, pas "abonnement" au sens strict.
    """
    without_digits = re.sub(r"\d+", "", normalize(libelle))
    return re.sub(r"\s+", " ", without_digits).strip()


# Un retrait DAB n'est pas une "charge" au sens de ce module : le montant
# est choisi par Cyril à chaque retrait, ce n'est pas un tarif qui pourrait
# "augmenter". Sans cette exclusion, des retraits au même distributeur
# (même libellé une fois les chiffres — dont le montant — retirés)
# groupent comme une charge récurrente, et une simple différence de
# montant entre deux retraits ressort comme une fausse hausse de tarif.
# ⚠️ Trouvé en validation réelle (09/08/2026, vrai historique de Cyril,
# vu seulement en comptages agrégés — jamais le contenu affiché) : deux
# retraits DAB au même distributeur signalés à +125 %/+122 % de "hausse".
_WITHDRAWAL_KEYWORDS = ("retrait", "distributeur")


def _is_cash_withdrawal(libelle: str) -> bool:
    normalized = normalize(libelle)
    if any(keyword in normalized for keyword in _WITHDRAWAL_KEYWORDS):
        return True
    return "dab" in normalized.split()


def _group_by_core_label(transactions: list[dict]) -> dict[str, list[dict]]:
    """
    Dépenses seulement (montant < 0), retraits DAB exclus — une charge
    récurrente est une sortie d'argent FACTURÉE.

    Réservé à _find_recurring_groups() (récurrence + hausses de tarif).
    detect_duplicate_charges() a un besoin opposé (garder les chiffres,
    pas les retirer) et regroupe via _duplicate_key() à la place — voir
    sa docstring pour le motif réel qui a rendu cette distinction
    nécessaire (09/08/2026, paires SOGECAP).
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for t in transactions:
        if t["montant"] >= 0:
            continue
        if _is_cash_withdrawal(t["libelle"]):
            continue
        core = _core_label(t["libelle"])
        if len(core) < MIN_CORE_LABEL_LEN:
            continue
        groups[core].append(t)
    return groups


def _find_recurring_groups(transactions: list[dict]) -> list[dict]:
    """
    Groupes reconnus comme récurrents — structure interne partagée par
    detect_recurring_charges() et detect_price_increases(), pour qu'un
    seul critère décide de ce qui compte comme récurrent, jamais deux
    définitions qui pourraient diverger entre les deux fonctions.
    """
    groups = []
    for core, occurrences in _group_by_core_label(transactions).items():
        occurrences = sorted(occurrences, key=lambda t: t["date"])
        if len(occurrences) < 2:
            continue

        amounts = [abs(t["montant"]) for t in occurrences]
        median = statistics.median(amounts)
        if median <= 0:
            continue
        occurrences = [
            t for t, a in zip(occurrences, amounts)
            if AMOUNT_SANITY_MIN_RATIO * median <= a <= AMOUNT_SANITY_MAX_RATIO * median
        ]
        if len(occurrences) < 2:
            continue

        gaps = [(b["date"] - a["date"]).days for a, b in itertools.pairwise(occurrences)]
        monthly_hits = sum(1 for g in gaps if MONTHLY_GAP_DAYS[0] <= g <= MONTHLY_GAP_DAYS[1])
        annual_hits = sum(1 for g in gaps if ANNUAL_GAP_DAYS[0] <= g <= ANNUAL_GAP_DAYS[1])

        # Mensuel exige 2 écarts conformes (3 occurrences) — "sur plusieurs
        # mois d'historique" (brief §3.1), pas une coïncidence à deux
        # points. Annuel exige 1 seul écart (2 occurrences) : réunir 2
        # écarts annuels demanderait 3 ans d'historique, peu réaliste.
        if monthly_hits >= 2:
            interval = "mensuel"
        elif annual_hits >= 1:
            interval = "annuel"
        else:
            continue

        groups.append({"core_label": core, "occurrences": occurrences, "interval": interval})
    return groups


def detect_recurring_charges(transactions: list[dict]) -> list[dict]:
    """Charges au motif régulier (même marchand, montant proche, intervalle constant)."""
    results = []
    for group in _find_recurring_groups(transactions):
        occurrences = group["occurrences"]
        median_amount = statistics.median(abs(t["montant"]) for t in occurrences)
        results.append({
            "status": "detecte",
            "core_label": group["core_label"],
            "sample_label": occurrences[-1]["libelle"],
            "category": occurrences[-1]["categorie"],
            "interval": group["interval"],
            "average_amount": round(-median_amount, 2),
            "occurrences": [
                {"date": t["date"].strftime("%Y-%m-%d"), "montant": round(t["montant"], 2)}
                for t in occurrences
            ],
        })
    return sorted(results, key=lambda r: r["average_amount"])  # plus négatif = plus gros, en premier


def detect_price_increases(transactions: list[dict]) -> list[dict]:
    """
    Hausses de tarif sur une charge déjà reconnue récurrente — compare
    chaque occurrence à la précédente dans le MÊME groupe, jamais deux
    marchands entre eux.
    """
    results = []
    for group in _find_recurring_groups(transactions):
        occurrences = group["occurrences"]
        for previous, current in itertools.pairwise(occurrences):
            prev_amount = abs(previous["montant"])
            new_amount = abs(current["montant"])
            increase = new_amount - prev_amount
            threshold = max(PRICE_INCREASE_MIN_ABSOLUTE, PRICE_INCREASE_MIN_RATIO * prev_amount)
            if increase <= threshold:
                continue
            results.append({
                "status": "detecte",
                "core_label": group["core_label"],
                "sample_label": current["libelle"],
                "category": current["categorie"],
                "previous_amount": round(-prev_amount, 2),
                "new_amount": round(-new_amount, 2),
                "previous_date": previous["date"].strftime("%Y-%m-%d"),
                "new_date": current["date"].strftime("%Y-%m-%d"),
                "increase_pct": round(increase / prev_amount * 100, 1),
            })
    return sorted(results, key=lambda r: -r["increase_pct"])


def _duplicate_key(libelle: str) -> str:
    """
    Clé de comparaison pour les doublons UNIQUEMENT : libellé COMPLET
    normalisé (minuscules, sans accents — core/text_utils.normalize()),
    SANS retrait des chiffres.

    À l'inverse de _core_label() (récurrence/hausses, qui A BESOIN de
    retirer les chiffres pour regrouper des occurrences dont seule la
    date/référence varie d'un mois à l'autre), un doublon doit au
    contraire GARDER le numéro de référence : c'est précisément ce qui
    distingue un vrai double prélèvement (même référence, débitée deux
    fois) de deux prélèvements légitimement différents qui partagent par
    coïncidence marchand, montant et jour.

    ⚠️ Trouvé en conditions réelles (09/08/2026, données de Cyril, revues
    par lui à l'écran, jamais affichées ici) : deux paires "PRLV EUROPEEN
    ACC <référence> DE: SOGECAP" à -5,00 €, même jour chaque mois, mais
    avec un numéro de référence DIFFÉRENT à chaque fois — deux contrats
    distincts, pas un doublon. _core_label() les confondait en un seul
    groupe parce qu'il retire justement ce numéro.
    """
    return normalize(libelle)


def detect_duplicate_charges(transactions: list[dict]) -> list[dict]:
    """
    Doublons probables — TOUJOURS retournés avec status="a_verifier"
    (RT-2, brief §5) : une ressemblance n'est jamais une preuve de double
    prélèvement, seulement une paire à vérifier soi-même.

    Regroupement dédié sur _duplicate_key() (libellé complet), PAS
    _group_by_core_label() — ce dernier reste réservé à
    _find_recurring_groups() (récurrence/hausses), qui a un besoin
    opposé (voir la docstring de _duplicate_key ci-dessus). Les retraits
    DAB restent exclus ici aussi : un retrait n'a pas de "charge" à
    dédoubler, même règle que pour les deux autres détecteurs.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for t in transactions:
        if t["montant"] >= 0:
            continue
        if _is_cash_withdrawal(t["libelle"]):
            continue
        key = _duplicate_key(t["libelle"])
        if len(key) < MIN_CORE_LABEL_LEN:
            continue
        groups[key].append(t)

    results = []
    for occurrences in groups.values():
        occurrences = sorted(occurrences, key=lambda t: t["date"])
        for a, b in itertools.pairwise(occurrences):
            gap_days = (b["date"] - a["date"]).days
            if gap_days > DUPLICATE_MAX_GAP_DAYS:
                continue
            if abs(abs(a["montant"]) - abs(b["montant"])) > DUPLICATE_AMOUNT_TOLERANCE:
                continue
            results.append({
                "status": "a_verifier",
                "transaction_1": {
                    "date": a["date"].strftime("%Y-%m-%d"), "libelle": a["libelle"],
                    "montant": round(a["montant"], 2),
                },
                "transaction_2": {
                    "date": b["date"].strftime("%Y-%m-%d"), "libelle": b["libelle"],
                    "montant": round(b["montant"], 2),
                },
                "gap_days": gap_days,
            })
    return results


def analyze(transactions: list[dict]) -> dict:
    """Instantané complet pour la carte Workspace "Détecteur d'économies"."""
    return {
        "recurring_charges": detect_recurring_charges(transactions),
        "price_increases": detect_price_increases(transactions),
        "duplicates": detect_duplicate_charges(transactions),
    }
