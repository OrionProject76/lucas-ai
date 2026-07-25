import unittest
from automation_manager import AutomationManager

class TestAutomation(unittest.TestCase):
    def test_open_chrome(self):
        manager = AutomationManager()
        result = manager.open_app("chrome")
        self.assertEqual(result, f"L'application chrome a été ouverte avec succès.")

    def test_open_calculatrice(self):
        manager = AutomationManager()
        result = manager.open_app("calculatrice")
        self.assertEqual(result, f"L'application calculatrice a été ouverte avec succès.")

if __name__ == "__main__":
    unittest.main()
