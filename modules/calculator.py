# modules/calculator.py — évaluation d'expressions arithmétiques
#
# ⚠️ SÉCURITÉ (corrigé le 02/08/2026, audit de fiabilité avant renommage) :
# l'implémentation précédente appelait eval(expression) directement, avec un
# commentaire affirmant à tort qu'il s'agissait d'une « évaluation sécurisée ».
# eval() exécute n'importe quel code Python, pas seulement des maths — par
# exemple eval("__import__('os').system('...')") lance une commande arbitraire.
# Ce module n'était appelé par rien d'autre dans le code au moment de la
# correction, mais son nom et son intention (« calculatrice ») en font un
# candidat naturel à exposer un jour comme outil appelable par le LLM — ce qui
# transformerait ce eval() en exécution de code arbitraire pilotable à
# distance (prompt injection depuis un document ou une page web lus par
# Luca's).
#
# Remplacé par un évaluateur limité à un sous-ensemble d'AST : nombres et
# opérateurs arithmétiques de base (+ - * / % ** parenthèses), rien d'autre.
# Toute expression qui sort de ce sous-ensemble est refusée, jamais exécutée.

from __future__ import annotations

import ast
import operator

_OPERATEURS_BINAIRES = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_OPERATEURS_UNAIRES = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


class InvalidExpression(Exception):
    """L'expression contient autre chose qu'une opération arithmétique simple."""


def _evaluer_noeud(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATEURS_BINAIRES:
        gauche = _evaluer_noeud(node.left)
        droite = _evaluer_noeud(node.right)
        return _OPERATEURS_BINAIRES[type(node.op)](gauche, droite)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATEURS_UNAIRES:
        return _OPERATEURS_UNAIRES[type(node.op)](_evaluer_noeud(node.operand))
    raise InvalidExpression(f"élément non autorisé : {ast.dump(node)}")


class Calculator:
    """Évalue une expression arithmétique, sans exécuter de code arbitraire."""

    def calculate(self, expression: str) -> float | int | None:
        """
        Évalue `expression`. Retourne None si l'expression est invalide,
        interdite, ou provoque une division par zéro — jamais une exception,
        pour que l'appelant n'ait qu'un seul cas à gérer.
        """
        try:
            arbre = ast.parse(expression, mode="eval")
            return _evaluer_noeud(arbre.body)
        except ZeroDivisionError:
            print("Erreur : Division par zéro")
            return None
        except (InvalidExpression, SyntaxError, TypeError, ValueError) as exc:
            print(f"Erreur : Expression invalide - {exc}")
            return None

    def test_expression(self, expression: str) -> bool:
        """
        Vrai si `expression` a pu être évaluée.

        ⚠️ calculate() ne lève jamais d'exception (voir ci-dessus) : cette
        méthode teste donc le résultat, pas une exception qui ne viendrait
        jamais — l'ancienne version enveloppait un appel qui ne pouvait pas
        échouer visiblement, et rendait toujours True.
        """
        return self.calculate(expression) is not None


if __name__ == "__main__":
    calculator = Calculator()
    print(calculator.test_expression("(45 + 32) * 2"))  # True — résultat 154
    print(calculator.test_expression("__import__('os')"))  # False — refusé
