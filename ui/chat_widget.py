import sys

from PySide6.QtWidgets import QApplication, QPushButton, QTextEdit

from modules.voice_manager import VoiceManager


class ChatWidget:
    def __init__(self, parent=None):
        self.parent = parent
        self.chat_area = self.create_chat_area()

    def create_chat_area(self):
        chat_area = QTextEdit()
        chat_area.setStyleSheet("""
            background-color: #1a1a2e;
            border-radius: 10px;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: center;
        """)
        return chat_area

    def show(self):
        self.parent.addWidget(self.chat_area)

    def add_lucas_button(self, text):
        """Ajoute un bouton '🔊 Lire' à côté de chaque message de Luca's"""
        button = QPushButton("🔊", self.chat_area)
        button.setStyleSheet("""
            background-color: transparent;
            border: none;
            padding: 5px;
            font-size: 12px;
            color: white;
        """)
        button.clicked.connect(lambda: self.play_lucas_audio(text))
        return button

    def play_lucas_audio(self, text):
        """Lecture du message de Luca's"""
        vm = VoiceManager()
        audio_path = vm.synthesize(text)
        if audio_path:
            vm.play_audio(audio_path)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    chat_widget = ChatWidget()
    chat_widget.show()
    sys.exit(app.exec())
