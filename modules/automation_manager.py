import subprocess
from typing import List

class AutomationManager:
    def __init__(self):
        self.applications_blanches = {
            "chrome": ["C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"],
            "calculatrice": ["C:\\Windows\\System32\\calc.exe"],
            "notepad": ["C:\\Windows\\System32\\notepad.exe"],
            "explorer": ["C:\\Windows\\Explorer.exe"],
            "cmd": ["C:\\Windows\\System32\\cmd.exe"]
        }

    def open_app(self, app_name: str) -> str:
        if app_name in self.applications_blanches:
            try:
                subprocess.Popen(self.applications_blanches[app_name])
                return f"L'application {app_name} a été ouverte avec succès."
            except Exception as e:
                return f"Erreur : l'application {app_name} n'a pas pu être ouverte. Erreur : {str(e)}"
        else:
            return "Application non autorisée"
