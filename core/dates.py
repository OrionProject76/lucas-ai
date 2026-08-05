# core/dates.py — reconnaître les périodes dans un texte ou un nom de fichier
#
# ── Pourquoi ce module existe ─────────────────────────────────────────
#
# La recherche vectorielle ne sait pas comparer des dates. Mesuré en
# conditions réelles : « Quel était mon salaire net en juillet 2025 ? »
# remontait les bulletins de février, avril et janvier 2026 — alors que
# le bulletin de juillet 2025 est bien indexé. Pour un modèle
# d'embeddings, « juillet 2025 » et « février 2026 » sont deux dates de
# bulletin de paie, donc sémantiquement voisines. Le mois demandé est
# précisément l'information qu'il écrase.
#
# Ce module extrait les périodes des DEUX côtés — des documents à
# l'indexation, de la question à la recherche — pour que rag_manager
# puisse filtrer ce que le sémantique a mélangé.
#
# ── Ce qu'est une « période » ─────────────────────────────────────────
#
# Une chaîne normalisée, comparable par simple égalité :
#     « 2025-07 »  un mois précis
#     « 2025 »     une année entière
# Un document porte souvent les deux : un bulletin de juillet 2025 est
# pertinent pour « juillet 2025 » comme pour « 2025 ».

from __future__ import annotations

import re

from core.text_utils import normalize

MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12,
}

# Bornes de vraisemblance. Sans elles, un numéro de sécurité sociale ou
# un montant fournit des « années » absurdes : « 1 77 06 56 121 075 »
# donnerait 1770, 5612, 1075…
MIN_YEAR, MAX_YEAR = 1990, 2100


def _valid(year: int, month: int | None = None) -> bool:
    if not MIN_YEAR <= year <= MAX_YEAR:
        return False
    return month is None or 1 <= month <= 12


def _add(periods: set[str], year: int, month: int | None = None) -> None:
    if not _valid(year, month):
        return
    periods.add(str(year))
    if month is not None:
        periods.add(f"{year}-{month:02d}")


def extract_periods(text: str) -> set[str]:
    """
    Toutes les périodes mentionnées dans un texte ou un nom de fichier.

    Volontairement LARGE côté document : mieux vaut qu'un bulletin soit
    associé à une période de trop que d'être introuvable au bon mois. La
    sélectivité vient de la question, pas de l'indexation.
    """
    found: set[str] = set()
    plain = normalize(text)

    # « juillet 2025 », « juillet2025 »
    for mois, numero in MONTHS.items():
        for match in re.finditer(rf"\b{mois}\s*(\d{{4}})\b", plain):
            _add(found, int(match.group(1)), numero)

    # 01/07/2025, 07-04-2026, 16.06.1977  (jour/mois/année, usage français)
    #
    # ⚠️ `\s*` autour des séparateurs depuis le 05/08/2026. Sans lui,
    # « 12 / 07 / 2025 » ne rendait que l'année, le mois était perdu — et
    # cette mise en forme est courante dans les PDF passés en mode
    # « layout », qui insèrent des espaces autour des séparateurs. Or
    # c'est exactement sur des bulletins de paie en PDF que la recherche
    # documentaire datée a été construite (§5.3).
    #
    # Trouvé en auditant les dépendances à la typographie — et il a
    # d'abord été pris pour l'une d'elles. Vérification faite : la
    # variante à espaces ASCII ordinaires échoue à l'identique, donc rien
    # à voir avec les caractères insécables. Corriger la typographie
    # ici aurait masqué la vraie cause sans la traiter.
    for d, m, y in re.findall(r"\b(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{4})\b", plain):
        _add(found, int(y), int(m))

    # 01/07/25 — année sur deux chiffres, bornée au siècle courant
    for d, m, y in re.findall(r"\b(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{2})\b", plain):
        _add(found, 2000 + int(y), int(m))

    # ⚠️ Les noms de fichiers de Cyril, qui portent l'essentiel de
    # l'information de date :
    #   bulletin-de-paie-du-010725-au-310725.pdf  -> JJMMAA
    #   bulletin-de-salaire-012026.pdf            -> MMAAAA
    # Les trois lectures sont tentées, et la validation tranche : un même
    # bloc de six chiffres ne peut être valide que dans un seul de ces
    # formats. « 010725 » n'est un AAAAMM que pour l'an 0107, « 012026 »
    # n'est un JJMMAA que pour le mois 20 — les deux sont écartés d'office.
    # ⚠️ Bloc ISOLÉ, encadré de non-chiffres. Sans cette borne, un
    # horodatage comme « 20260408.120900 » livrait « 2000-09 » en
    # découpant l'heure, et un identifiant de dix chiffres inventait des
    # périodes au hasard. Les vrais formats de Cyril — « 012026 »,
    # « 010725-au-310725 » — sont tous isolés.
    for bloc in re.findall(r"(?<!\d)(\d{6})(?!\d)", plain):
        _add(found, 2000 + int(bloc[4:]), int(bloc[2:4]))   # JJMMAA
        _add(found, int(bloc[2:]), int(bloc[:2]))           # MMAAAA
        _add(found, int(bloc[:4]), int(bloc[4:]))           # AAAAMM

    # ⚠️ Années isolées — PAS de \b ici. « Carrière2026 » et « Cv2026 »
    # ne présentent aucune frontière de mot entre la lettre et le
    # chiffre : \b n'y voyait rien, et deux documents de Cyril se
    # retrouvaient sans aucune date. Ce qu'il faut exclure, ce sont les
    # chiffres voisins, pas les lettres.
    for annee in re.findall(r"(?<!\d)(\d{4})(?!\d)", plain):
        _add(found, int(annee))

    return found


def extract_query_period(question: str) -> str | None:
    """
    La période que la question DEMANDE, ou None si elle n'en nomme aucune.

    ⚠️ Contrairement à extract_periods(), cette fonction est
    volontairement STRICTE et ne rend qu'une seule valeur. Filtrer sur
    une période que Cyril n'a pas demandée écarterait des documents
    pertinents — et une question sans date ne doit rien filtrer du tout.

    Le mois l'emporte sur l'année : « juillet 2025 » rend « 2025-07 »,
    qui est plus sélectif.
    """
    plain = normalize(question)

    for mois, numero in MONTHS.items():
        # « juillet 2025 »
        match = re.search(rf"\b{mois}\s+(\d{{4}})\b", plain)
        if match and _valid(int(match.group(1)), numero):
            return f"{int(match.group(1))}-{numero:02d}"
        # « en juillet », sans année : trop ambigu pour filtrer — quel
        # juillet ? Sur cinq ans de bulletins, se tromper d'année est
        # aussi gênant que se tromper de mois.
        if re.search(rf"\b{mois}\b", plain):
            return None

    # « 01/07/2025 »
    match = re.search(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b", plain)
    if match:
        mois_num, annee = int(match.group(2)), int(match.group(3))
        if _valid(annee, mois_num):
            return f"{annee}-{mois_num:02d}"

    # « en 2025 », « de 2026 » — l'année seule reste utile pour trier
    # cinq ans de documents.
    match = re.search(r"\b(19|20)\d{2}\b", plain)
    if match and _valid(int(match.group(0))):
        return match.group(0)

    return None


def matches(period: str, document_periods: str) -> bool:
    """
    Ce document couvre-t-il la période demandée ?

    `document_periods` est la métadonnée stockée à l'indexation, sous
    forme de chaîne séparée par des virgules — ChromaDB n'accepte pas de
    liste en métadonnée, et le filtrage se fait donc en Python.

    Une demande d'ANNÉE accepte tous ses mois : « 2025 » retient un
    document de juillet 2025. Une demande de MOIS est stricte.
    """
    connues = set(document_periods.split(",")) if document_periods else set()
    if period in connues:
        return True
    # Demande d'année : « 2025 » couvre « 2025-07 »
    if "-" not in period:
        return any(p.startswith(f"{period}-") for p in connues)
    return False
