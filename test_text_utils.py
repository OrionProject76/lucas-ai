# test_text_utils.py — normalisation avant comparaison de mots-clés
#
# Ce module a été écrit après un bug trouvé en usage réel, pas en revue :
# « analyse mes depenses du mois », tapé sans accents, échappait au
# filtre de sensibilité et partait au CLOUD. La règle 3 de CLAUDE.md
# était contournable par une faute de frappe.

from __future__ import annotations

import pytest

from core.text_utils import contains_any, normalize

# ── normalize() ───────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Dépense", "depense"),
        ("RELEVÉ", "releve"),
        ("Crédit Immobilier", "credit immobilier"),
        ("écran", "ecran"),
        ("À l'écran", "a l'ecran"),
        ("déjà vu", "deja vu"),
    ],
)
def test_accents_and_case_are_removed(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


@pytest.mark.parametrize("apostrophe", ["’", "‘", "ʼ", "´", "`"])
def test_every_apostrophe_variant_is_unified(apostrophe: str) -> None:
    """
    Windows, macOS et les correcteurs automatiques produisent des
    apostrophes différentes. Toutes doivent se ramener à la même.
    """
    assert normalize(f"qu{apostrophe}est-ce") == "qu'est-ce"


def test_already_normalised_text_is_unchanged() -> None:
    assert normalize("mes depenses du mois") == "mes depenses du mois"


def test_empty_string_survives() -> None:
    assert normalize("") == ""


# ── contains_any() ────────────────────────────────────────────────────

def test_keywords_are_normalised_too() -> None:
    """
    Le piège qui rendait la correction inutile : normaliser le texte mais
    comparer à des mots-clés accentués ne matche plus rien du tout.
    """
    assert contains_any("mes depenses", ["dépense"])
    assert contains_any("mes dépenses", ["depense"])


def test_curly_apostrophe_in_text_matches_straight_keyword() -> None:
    assert contains_any("qu’est-ce que tu vois à l’écran", ["à l'écran"])


def test_no_false_positive() -> None:
    assert not contains_any("quelle heure il est", ["dépense", "à l'écran"])


def test_empty_keyword_list_matches_nothing() -> None:
    assert not contains_any("n'importe quoi", [])


# ── Cohérence entre les modules ───────────────────────────────────────

def test_every_keyword_matcher_uses_the_shared_normalisation() -> None:
    """
    Chaque liste de mots-clés est une garde de sécurité. Une seule qui
    compare le texte brut rouvre la faille — d'où cette vérification à
    l'échelle des modules concernés.
    """
    import inspect

    from core import router
    from modules import finance_categorizer, web_search

    for module in (router, web_search, finance_categorizer):
        source = inspect.getsource(module)
        assert "text_utils" in source, (
            f"{module.__name__} doit utiliser la normalisation partagée"
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
