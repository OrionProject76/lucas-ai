import sys
import random
from PySide6.QtWidgets import QWidget, QApplication, QVBoxLayout, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPainter, QColor, QRadialGradient, QBrush, QPen, QFont

class AvatarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(140, 140)
        # WA_TransparentBackground n'existe pas dans Qt : l'attribut correct
        # est WA_TranslucentBackground. Ce bug empêchait l'avatar — donc
        # toute l'interface — de démarrer.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.state = "IDLE"
        self.mouth_open = 0.0
        self.glow_intensity = 0.5
        self.glow_direction = 1
        self.eye_blink = False
        self.blink_timer = 0
        self.particles = []
        self.mouse_pos = QPointF(70, 70)

        # Timer animation globale (60fps)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.start(50)  # 20fps

        # Timer clignement aléatoire
        self.blink_timer_obj = QTimer(self)
        self.blink_timer_obj.timeout.connect(self.trigger_blink)
        self.blink_timer_obj.start(3000)

        self.setMouseTracking(True)

    def set_state(self, state):
        self.state = state
        self.update()

    def update_mouth(self, open_ratio):
        self.mouth_open = max(0.0, min(1.0, open_ratio))
        self.update()

    def trigger_blink(self):
        if self.state == "IDLE":
            self.eye_blink = True
            self.blink_timer = 3
            QTimer.singleShot(150, self.end_blink)

    def end_blink(self):
        self.eye_blink = False
        self.update()

    def update_animation(self):
        # Glow pulsation
        if self.state == "IDLE":
            self.glow_intensity += 0.02 * self.glow_direction
            if self.glow_intensity >= 0.8:
                self.glow_direction = -1
            elif self.glow_intensity <= 0.3:
                self.glow_direction = 1
        elif self.state == "LISTENING":
            self.glow_intensity = 0.9 + 0.1 * random.random()
        elif self.state == "THINKING":
            self.glow_intensity = 0.7 + 0.3 * random.random()
            # Particules
            if random.random() > 0.7:
                self.particles.append({
                    'x': 70 + random.randint(-40, 40),
                    'y': 70 + random.randint(-20, 20),
                    'size': random.randint(2, 5),
                    'life': 1.0,
                    'speed': random.uniform(0.5, 2.0)
                })
            for p in self.particles:
                p['y'] -= p['speed']
                p['life'] -= 0.05
            self.particles = [p for p in self.particles if p['life'] > 0]
        elif self.state == "SPEAKING":
            self.mouth_open = 0.3 + 0.4 * abs(random.random() - 0.5) * 2
            self.glow_intensity = 0.6

        self.update()

    def mouseMoveEvent(self, event):
        self.mouse_pos = QPointF(event.pos())
        self.update()

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
        body_gradient.setColorAt(0, QColor(20, 20, 40))
        body_gradient.setColorAt(0.7, QColor(10, 10, 25))
        body_gradient.setColorAt(1, QColor(0, 212, 255, 100))

        painter.setBrush(QBrush(body_gradient))
        pen = QPen(QColor(0, 212, 255, 150), 2)
        painter.setPen(pen)
        painter.drawEllipse(center, 45, 45)

        # Yeux
        if not self.eye_blink:
            # Calcul direction yeux (suivent la souris)
            dx = self.mouse_pos.x() - center.x()
            dy = self.mouse_pos.y() - center.y()
            dist = (dx**2 + dy**2) ** 0.5
            if dist > 0:
                eye_offset_x = (dx / dist) * 8
                eye_offset_y = (dy / dist) * 6
            else:
                eye_offset_x = eye_offset_y = 0

            # Œil gauche
            left_eye = QPointF(55 + eye_offset_x, 60 + eye_offset_y)
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(left_eye, 8, 10)

            # Pupille gauche
            pupil_l = QPointF(left_eye.x() + eye_offset_x * 0.3, left_eye.y() + eye_offset_y * 0.3)
            painter.setBrush(QBrush(QColor(0, 212, 255)))
            painter.drawEllipse(pupil_l, 3, 4)

            # Œil droit
            right_eye = QPointF(85 + eye_offset_x, 60 + eye_offset_y)
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            painter.drawEllipse(right_eye, 8, 10)

            # Pupille droite
            pupil_r = QPointF(right_eye.x() + eye_offset_x * 0.3, right_eye.y() + eye_offset_y * 0.3)
            painter.setBrush(QBrush(QColor(0, 212, 255)))
            painter.drawEllipse(pupil_r, 3, 4)
        else:
            # Yeux fermés (lignes)
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawLine(47, 60, 63, 60)
            painter.drawLine(77, 60, 93, 60)

        # Bouche
        painter.setPen(QPen(QColor(0, 212, 255, 200), 2))
        mouth_y = 85
        mouth_width = 20
        mouth_height = int(8 * self.mouth_open)

        if mouth_height < 2:
            # Bouche fermée (ligne)
            painter.drawLine(60, mouth_y, 80, mouth_y)
        else:
            # Bouche ouverte (arc)
            painter.setBrush(QBrush(QColor(20, 10, 30)))
            painter.drawEllipse(60, mouth_y - mouth_height//2, mouth_width, mouth_height)

        # Particules (état THINKING)
        if self.state == "THINKING":
            for p in self.particles:
                alpha = int(p['life'] * 255)
                painter.setBrush(QBrush(QColor(0, 212, 255, alpha)))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPointF(p['x'], p['y']), p['size'], p['size'])

        # Label état
        painter.setPen(QPen(QColor(0, 212, 255, 150), 1))
        painter.setFont(QFont("Consolas", 7))
        painter.drawText(50, 130, 40, 15, Qt.AlignCenter, self.state)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = QWidget()
    window.setWindowTitle("Test Avatar Orion")
    window.setFixedSize(300, 400)
    window.setStyleSheet("background-color: #0a0a0a;")

    layout = QVBoxLayout()

    avatar = AvatarWidget()
    layout.addWidget(avatar, alignment=Qt.AlignCenter)

    btn_layout = QHBoxLayout()

    for state in ["IDLE", "LISTENING", "THINKING", "SPEAKING"]:
        btn = QPushButton(state)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #1a1a2e;
                color: #00d4ff;
                border: 1px solid #00d4ff;
                border-radius: 5px;
                padding: 8px;
                font-family: Consolas;
            }
            QPushButton:hover {
                background-color: #00d4ff;
                color: #0a0a0a;
            }
        """)
        btn.clicked.connect(lambda checked, s=state: avatar.set_state(s))
        btn_layout.addWidget(btn)

    layout.addLayout(btn_layout)

    # Bouton test bouche
    mouth_btn = QPushButton("Test Bouche (parler)")
    mouth_btn.setStyleSheet("""
        QPushButton {
            background-color: #16213e;
            color: #7c3aed;
            border: 1px solid #7c3aed;
            border-radius: 5px;
            padding: 10px;
            font-family: Consolas;
        }
    """)

    import math
    def animate_mouth():
        import time
        for i in range(20):
            avatar.update_mouth(0.5 + 0.5 * math.sin(i * 0.5))
            QApplication.processEvents()
            time.sleep(0.1)
        avatar.update_mouth(0.0)

    mouth_btn.clicked.connect(animate_mouth)
    layout.addWidget(mouth_btn)

    window.setLayout(layout)
    window.show()

    sys.exit(app.exec())
