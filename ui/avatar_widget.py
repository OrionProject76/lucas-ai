import sys
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QBrush
from PySide6.QtCore import Qt, QTimer, QPoint
import math


class AvatarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.width = 120
        self.height = 120
        self.eye_radius = 10
        self.mouth_radius = 20
        self.state = "IDLE"
        self.timer_idle = QTimer(self)
        self.timer_listening = QTimer(self)
        self.timer_thinking = QTimer(self)
        self.timer_speaking = QTimer(self)

        self.timer_idle.timeout.connect(self.idle_animation)
        self.timer_listening.timeout.connect(self.listening_animation)
        self.timer_thinking.timeout.connect(self.thinking_animation)
        self.timer_speaking.timeout.connect(self.speaking_animation)

        self.eye_x = 0
        self.eye_y = 0

    def paintEvent(self, event):
        qp = QPainter()
        qp.begin(self)
        self.draw_avatar(qp)
        qp.end()

    def draw_avatar(self, qp):
        # Fond
        qp.setBrush(QBrush(QColor("#00d4ff")))
        qp.setPen(QPen(Qt.NoPen))
        qp.drawRect(0, 0, self.width, self.height)

        # Dégradé
        gradient = QLinearGradient(0, 0, self.width, self.height)
        gradient.setColorAt(0.0, QColor("#00d4ff"))
        gradient.setColorAt(1.0, QColor("#7c3aed"))
        qp.setBrush(QBrush(gradient))
        qp.drawRect(0, 0, self.width, self.height)

        # Yeux
        qp.setPen(QPen(Qt.NoPen))
        qp.setBrush(QBrush(QColor("white")))
        qp.drawEllipse(self.eye_x - self.eye_radius, self.eye_y - self.eye_radius,
                       self.eye_radius * 2, self.eye_radius * 2)
        qp.drawEllipse(self.eye_x + self.eye_radius, self.eye_y - self.eye_radius,
                       self.eye_radius * 2, self.eye_radius * 2)

        # Bouche
        qp.setPen(QPen(Qt.NoPen))
        qp.setBrush(QBrush(QColor("white")))
        qp.drawArc(0, self.height / 2 - self.mouth_radius, self.width, self.mouth_radius * 2,
                   int(-64 * math.pi / 180), int(128 * math.pi / 180))

    def mouseMoveEvent(self, event):
        self.eye_x = event.pos().x()
        self.eye_y = event.pos().y()

    def set_state(self, state):
        self.state = state
        if state == "IDLE":
            self.timer_idle.start(1000)
            self.timer_listening.stop()
            self.timer_thinking.stop()
            self.timer_speaking.stop()
        elif state == "LISTENING":
            self.timer_listening.start(300)
            self.timer_idle.stop()
            self.timer_thinking.stop()
            self.timer_speaking.stop()
        elif state == "THINKING":
            self.timer_thinking.start(1000)
            self.timer_idle.stop()
            self.timer_listening.stop()
            self.timer_speaking.stop()
        elif state == "SPEAKING":
            self.timer_speaking.start(500)
            self.timer_idle.stop()
            self.timer_listening.stop()
            self.timer_thinking.stop()

    def update_mouth(self, open_ratio):
        qp = QPainter()
        qp.begin(self)
        self.draw_avatar(qp)
        qp.end()

    def idle_animation(self):
        # Clignement aléatoire
        if self.state == "IDLE":
            self.eye_x += 5
            if self.eye_x > self.width:
                self.eye_x = -self.eye_radius

    def listening_animation(self):
        # Pulsation rapide
        qp = QPainter()
        qp.begin(self)
        self.draw_avatar(qp)
        qp.end()

    def thinking_animation(self):
        # Particules flottantes
        qp = QPainter()
        qp.begin(self)
        self.draw_avatar(qp)
        qp.end()

    def speaking_animation(self):
        # Bouche qui s'ouvre/ferme
        open_ratio = 0.5
        qp = QPainter()
        qp.begin(self)
        self.draw_avatar(qp)
        qp.end()


test_avatar.py
