# ui/main_window.py — interface Orion AI
# Streaming fluide, indicateur de connexion, bouton Stop, scroll auto

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QLineEdit, QPushButton, QLabel, QHBoxLayout
)
from PySide6.QtCore import Qt

from core.orion_core import OrionCore
from core.llm_worker import LLMWorker
from config import WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT


DARK_STYLE = """
QWidget {
    background-color: #0D0D12;
    color: #E8EAED;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 14px;
}
QTextEdit {
    background-color: #14141A;
    border: 1px solid #2A2C38;
    border-radius: 10px;
    padding: 12px;
    color: #E8EAED;
    line-height: 1.5;
}
QLineEdit {
    background-color: #14141A;
    border: 1px solid #2A2C38;
    border-radius: 10px;
    padding: 10px 14px;
    color: #E8EAED;
    font-size: 14px;
}
QLineEdit:focus {
    border: 1px solid #00D4FF;
}
QPushButton {
    background-color: #1E88E5;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 14px;
}
QPushButton:hover {
    background-color: #00D4FF;
}
QPushButton:disabled {
    background-color: #2A2C38;
    color: #6B6F7B;
}
QPushButton#stop {
    background-color: #E53935;
}
QPushButton#stop:hover {
    background-color: #FF5252;
}
QLabel#title {
    font-size: 22px;
    font-weight: bold;
    color: #00D4FF;
    padding: 10px;
    letter-spacing: 2px;
}
QLabel#status {
    color: #FFB300;
    font-style: italic;
    font-size: 12px;
    padding: 4px 8px;
    background-color: #1A1A24;
    border-radius: 6px;
}
QLabel#status_connecting {
    color: #FFB300;
}
QLabel#status_thinking {
    color: #00D4FF;
}
"""


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.orion = OrionCore()
        self.worker = None

        self.setWindowTitle(WINDOW_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(DARK_STYLE)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # --- Titre ---
        title = QLabel("◈ ORION AI ◈")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)

        # --- Zone de chat ---
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # --- Barre de statut ---
        self.status_label = QLabel("")
        self.status_label.setObjectName("status")
        self.status_label.setVisible(False)

        # --- Zone de saisie + boutons ---
        input_layout = QHBoxLayout()
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Parle à Orion...")
        self.input_field.returnPressed.connect(self.send_message)

        self.send_button = QPushButton("Envoyer")
        self.send_button.setFixedWidth(100)
        self.send_button.clicked.connect(self.send_message)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("stop")
        self.stop_button.setFixedWidth(80)
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.stop_generation)

        input_layout.addWidget(self.input_field, stretch=1)
        input_layout.addWidget(self.send_button)
        input_layout.addWidget(self.stop_button)

        # --- Assemblage ---
        layout.addWidget(title)
        layout.addWidget(self.chat_history, stretch=1)
        layout.addWidget(self.status_label)
        layout.addLayout(input_layout)

        self.setLayout(layout)
        self._load_history()

    def _load_history(self):
        for role, message in self.orion.history():
            self._append(role, message)

    def _append(self, role: str, message: str):
        speaker = "Cyril" if role == "user" else "Orion"
        color = "#00D4FF" if role == "user" else "#E8EAED"
        self.chat_history.append(
            f'<span style="color:{color};"><b>{speaker} :</b></span> {message}'
        )

    def send_message(self):
        text = self.input_field.text().strip()
        if not text:
            return

        self._append("user", text)
        self.input_field.clear()

        messages = self.orion.prepare(text)

        # UI en mode "attente"
        self.send_button.setVisible(False)
        self.stop_button.setVisible(True)
        self.input_field.setEnabled(False)
        
        self.status_label.setText("⏳ Connexion à Ollama...")
        self.status_label.setObjectName("status status_connecting")
        self.status_label.setVisible(True)
        
        self.chat_history.append('<span style="color:#E8EAED;"><b>Orion :</b></span> ')

        # Lancer le worker
        self.worker = LLMWorker(messages)
        self.worker.started_thinking.connect(self._on_started)
        self.worker.token_received.connect(self._on_token)
        self.worker.response_complete.connect(self._on_complete)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.start()

    def _on_started(self):
        """Appelé quand la connexion est établie et Ollama répond."""
        self.status_label.setText("💭 Orion réfléchit...")
        self.status_label.setObjectName("status status_thinking")

    def _on_token(self, token: str):
        """Chaque token reçu — on l'affiche en temps réel."""
        if self.status_label.isVisible():
            self.status_label.setVisible(False)

        cursor = self.chat_history.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(token)
        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()  # Scroll auto

    def _on_complete(self, full_answer: str):
        self.orion.save_response(full_answer)
        self._unlock_input()

    def _on_error(self, error_message: str):
        self.status_label.setVisible(False)
        self._append("assistant", error_message)
        self._unlock_input()

    def stop_generation(self):
        """Arrête la génération en cours."""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self._append("assistant", "[Génération interrompue]")
            self._unlock_input()

    def _unlock_input(self):
        self.send_button.setVisible(True)
        self.stop_button.setVisible(False)
        self.send_button.setEnabled(True)
        self.input_field.setEnabled(True)
        self.input_field.setFocus()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
        self.orion.close()