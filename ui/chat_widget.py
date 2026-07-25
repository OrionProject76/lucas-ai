import sys
from PyQt5.QtWidgets import QTextEdit, QWidget

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
