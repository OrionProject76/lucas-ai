import sys
from PyQt5.QtCore import pyqtSignal

class ChatWidget:
    def __init__(self):
        self.token_signal = pyqtSignal(str)

    def connect_signals(self):
        # Connecter le signal pour afficher les tokens au fur et à mesure dans la bulle Orion
        self.token_signal.connect(self.display_token)

    def display_token(self, token):
        print(f"Token affiché : {token}")
