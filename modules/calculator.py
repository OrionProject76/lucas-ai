import re

class Calculator:
    def calculate(self, expression):
        try:
            # Évaluation de l'expression mathématique sécurisée
            result = eval(expression)
            return result
        except ZeroDivisionError:
            print("Erreur : Division par zéro")
            return None
        except Exception as e:
            print(f"Erreur : Expression invalide - {e}")
            return None

    def test_expression(self, expression):
        # Test de l'expression mathématique
        try:
            self.calculate(expression)
            return True
        except Exception:
            return False

if __name__ == "__main__":
    calculator = Calculator()
    print(calculator.test_expression("15% de 2340"))  # Résultat attendu : 351.9
    print(calculator.test_expression("(45 + 32) * 2"))  # Résultat attendu : 154
