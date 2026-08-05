# test_dependance_forme.py — aucun mécanisme ne doit dépendre de la FORME
# du texte plutôt que de son sens
#
# ⚠️ D'où vient ce fichier (05/08/2026, ROADMAP.md §5.50)
# ---------------------------------------------------------------------
# Après la bascule sur gpt-oss:20b, six mécanismes sur sept s'étaient
# révélés aveugles — dont deux gardes de sécurité — parce qu'ils
# reconnaissaient une FORME d'écriture et non un sens. Cyril a demandé de
# chercher s'il en restait d'autres.
#
# Il en restait, et l'un était une vraie fuite : le filtre anti-fuite de
# la recherche web appliquait ses motifs IBAN/carte à la chaîne BRUTE,
# avec l'espace ASCII codé en dur. Un IBAN copié depuis un site bancaire
# — qui emploie des espaces INSÉCABLES pour que le numéro ne se coupe pas
# en fin de ligne — partait chez DuckDuckGo.
#
# Ces tests couvrent les quatre mécanismes trouvés, et existent surtout
# pour qu'un futur ajout de motif ne réintroduise pas la même classe de
# faille.

from __future__ import annotations

import pytest

from core.dates import extract_periods
from core.router import extract_calculation, extract_city
from core.text_utils import fold_separators, normalize
from modules.calculator import Calculator
from modules.web_search import is_identifying

NBSP = " "   # espace insécable
FINE = " "   # espace fine insécable — employée par gpt-oss
INSEC = "‑"  # trait d'union insécable


# ── 🔴 Le filtre anti-fuite : la seule surface qui sort de la machine ──
#
# Numéros FABRIQUÉS, format valide, aucun lien avec Cyril.

IBAN = "FR76 3000 4000 0512 3456 7890 123"
CARTE = "4539 1488 0343 6467"


@pytest.mark.parametrize("separateur", [" ", NBSP, FINE, ""])
def test_an_iban_is_blocked_whatever_the_spacing(separateur: str) -> None:
    """
    Les sites bancaires et les PDF affichent les IBAN avec des espaces
    INSÉCABLES, précisément pour que le numéro ne soit pas coupé en fin
    de ligne. Un copier-coller depuis la banque les emporte — et c'est
    exactement le geste qu'on fait pour poser une question sur son IBAN.
    """
    requete = f"cherche des infos sur {IBAN.replace(' ', separateur)}"
    assert is_identifying(requete), "un IBAN ne doit JAMAIS partir chez DuckDuckGo"


@pytest.mark.parametrize("separateur", [" ", NBSP, FINE, "-", INSEC, ""])
def test_a_card_number_is_blocked_whatever_the_spacing(separateur: str) -> None:
    requete = f"que vaut {CARTE.replace(' ', separateur)}"
    assert is_identifying(requete)


@pytest.mark.parametrize(
    "requete",
    ["météo à Paris", "recette de la tarte tatin", "prix du RTX 5080 en 2026"],
)
def test_an_ordinary_query_is_not_blocked(requete: str) -> None:
    """
    Garde-fou symétrique : un filtre qui bloque tout ne protège rien, il
    supprime juste la fonctionnalité.
    """
    assert not is_identifying(requete)


# ── Extraction de ville (météo) ───────────────────────────────────────


@pytest.mark.parametrize("tiret", ["-", INSEC])
def test_a_hyphenated_city_survives_any_hyphen(tiret: str) -> None:
    """« Saint‑Étienne » avec U+2011 rendait « Saint » — donc la météo
    d'une autre ville, ou aucune."""
    ville = extract_city(f"quel temps fait-il à Saint{tiret}Étienne ?")
    assert ville is not None and "tienne" in ville


def test_the_extracted_city_keeps_its_accents() -> None:
    """
    ⚠️ C'est pourquoi `fold_separators` existe à côté de `normalize` :
    la valeur extraite part vers le service météo ET s'affiche à Cyril.
    La passer par normalize() rendrait « saint-etienne » — on abîmerait
    la donnée pour corriger un problème de séparateur.
    """
    assert extract_city("quel temps fait-il à Nîmes ?") == "Nîmes"


# ── Extraction de calcul ──────────────────────────────────────────────


@pytest.mark.parametrize("separateur", [" ", NBSP, FINE])
def test_french_thousands_grouping_is_computed(separateur: str) -> None:
    expression = extract_calculation(f"combien fait 1{separateur}234 + 5{separateur}678 ?")
    assert Calculator().calculate(expression) == 6912


def test_two_digit_groups_are_never_glued() -> None:
    """
    La règle exige TROIS chiffres après l'espace — le groupement français
    des milliers, et rien d'autre. Recoller « 12 34 » en « 1234 » serait
    une lecture inventée, pas une correction de typographie.
    """
    assert extract_calculation("combien fait 12 34 + 5 ?") == "12 34 + 5"


def test_a_non_breaking_hyphen_still_reads_as_a_minus() -> None:
    assert Calculator().calculate(extract_calculation(f"combien fait 5678 {INSEC} 1234 ?")) == 4444


# ── Dates dans les documents ──────────────────────────────────────────


@pytest.mark.parametrize("espace", ["", " ", NBSP])
def test_a_date_with_spaces_around_separators_keeps_its_month(espace: str) -> None:
    """
    ⚠️ Trouvé en cherchant une dépendance à la typographie, et ce n'en
    était PAS une : la variante à espaces ASCII ordinaires échouait à
    l'identique. Un PDF passé en mode « layout » insère couramment ces
    espaces — et c'est sur des bulletins de paie en PDF que la recherche
    documentaire datée a été construite.
    """
    periodes = extract_periods(f"bulletin du 12{espace}/{espace}07{espace}/{espace}2025")
    assert "2025-07" in periodes, "le mois est perdu, la recherche datée échouera"


# ── Les deux outils, et leur différence ───────────────────────────────


def test_normalize_is_for_comparing_and_destroys_information() -> None:
    assert normalize("Saint-Étienne") == "saint-etienne"


def test_fold_separators_is_for_extracting_and_preserves_the_value() -> None:
    assert fold_separators(f"Saint{INSEC}Étienne") == "Saint-Étienne"
    assert fold_separators(f"1{FINE}234") == "1 234"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
