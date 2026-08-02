# test_calculator.py — évaluateur d'expressions arithmétiques
#
# Le point qui compte : calculate() ne doit JAMAIS exécuter autre chose que
# de l'arithmétique. L'ancienne implémentation appelait eval() directement
# en le qualifiant à tort de « sécurisé » — ces tests vérifient le remplacement
# par un évaluateur limité à un sous-ensemble d'AST.

from __future__ import annotations

import pytest

from modules.calculator import Calculator


@pytest.fixture
def calc():
    return Calculator()


def test_addition_simple(calc):
    assert calc.calculate("2 + 2") == 4


def test_priorite_des_operateurs(calc):
    assert calc.calculate("(45 + 32) * 2") == 154


def test_division(calc):
    assert calc.calculate("9 / 2") == 4.5


def test_puissance(calc):
    assert calc.calculate("2 ** 10") == 1024


def test_nombre_negatif(calc):
    assert calc.calculate("-5 + 3") == -2


def test_division_par_zero_ne_leve_pas(calc):
    """Signalée, pas une exception qui remonterait jusqu'à l'appelant."""
    assert calc.calculate("1 / 0") is None


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('echo test')",
        "__import__('os')",
        "open('/etc/passwd')",
        "[x for x in ().__class__.__bases__]",
        "1; import os",
    ],
)
def test_aucun_code_arbitraire_n_est_execute(calc, expression):
    """
    LE test qui compte : c'est exactement ce que l'ancien eval() direct
    aurait exécuté sans broncher. Doit être refusé, jamais lancé.
    """
    assert calc.calculate(expression) is None


def test_expression_invalide_est_refusee(calc):
    assert calc.calculate("2 + ") is None


def test_expression_avec_nom_est_refusee(calc):
    """Un nom (variable, fonction) n'est pas un nombre : refusé, pas résolu."""
    assert calc.calculate("un_nom_quelconque") is None


def test_expression_valide_est_signalee_comme_telle(calc):
    assert calc.test_expression("(45 + 32) * 2") is True


def test_expression_invalide_est_signalee_comme_telle(calc):
    assert calc.test_expression("__import__('os')") is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
