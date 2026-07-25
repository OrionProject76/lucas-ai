import sys
from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtGui import QColor

class AvatarWidget:
    def __init__(self, parent=None):
        self.parent = parent
        self.avatar = self.create_avatar()

    def create_avatar(self):
        avatar = QLabel()
        avatar.setStyleSheet("""
            background-color: #00d4ff;
            border-radius: 40px;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: center;
        """)
        return avatar

    def set_state(self, state):
        if state == 'IDLE':
            self.avatar.setStyleSheet("""
                background-color: #00d4ff;
                border-radius: 40px;
                padding: 20px;
                display: flex;
                justify-content: center;
                align-items: center;
            """)
        elif state == 'LISTENING':
            self.avatar.setStyleSheet("""
                background-color: #7c3aed;
                border-radius: 40px;
                padding: 20px;
                display: flex;
                justify-content: center;
                align-items: center;
            """)
        elif state == 'THINKING':
            self.avatar.setStyleSheet("""
                background-color: #00d4ff;
                border-radius: 40px;
                padding: 20px;
                display: flex;
                justify-content: center;
                align-items: center;
            """)
        elif state == 'SPEAKING':
            self.avatar.setStyleSheet("""
                background-color: #7c3aed;
                border-radius: 40px;
                padding: 20px;
                display: flex;
                justify-content: center;
                align-items: center;
            """)

    def show(self):
        self.parent.addWidget(self.avatar)
