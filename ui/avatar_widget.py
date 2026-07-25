import sys
import random
from PySide6.QtWidgets import QWidget, QApplication, QVBoxLayout, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPainter, QColor, QRadialGradient, QBrush, QPen, QFont

class AvatarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(140, 140)
        self.setAttribute(Qt.WA_TransparentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint)

        # ... (le reste du code reste inchangé)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center = QPointF(70, 70)

        # Glow externe
        glow_radius = 55 + self.glow_intensity * 10
        gradient = QRadialGradient(center, glow_radius)

        if self.state == "IDLE":
            alpha = int(self.glow_intensity * 60)
            gradient.setColorAt(0, QColor(0, 212, 255, alpha))
            gradient.setColorAt(1, QColor(124, 58, 237, 0))
        elif self.state == "LISTENING":
            gradient.setColorAt(0, QColor(0, 212, 255, 100))
            gradient.setColorAt(1, QColor(0, 212, 255, 0))
        elif self.state == "THINKING":
            gradient.setColorAt(0, QColor(124, 58, 237, 120))
            gradient.setColorAt(1, QColor(124, 58, 237, 0))
        elif self.state == "SPEAKING":
            gradient.setColorAt(0, QColor(0, 212, 255, 80))
            gradient.setColorAt(1, QColor(124, 58, 237, 40))

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, glow_radius, glow_radius)

        # Corps principal (cercle)
        body_gradient = QRadialGradient(center, 45)
        body_gradient.setColorAt(0, QColor(20, 20, 40))  # Modifié ici
        body_gradient.setColorAt(0.7, QColor(10, 10, 25))
        body_gradient.setColorAt(1, QColor(0, 212, 255, 100))

        painter.setBrush(QBrush(body_gradient))
        pen = QPen(QColor(0, 212, 255, 150), 2)
        painter.setPen(pen)
        painter.drawEllipse(center, 45, 45)

        # ... (le reste du code reste inchangé)
