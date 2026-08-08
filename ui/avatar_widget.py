import math
import random
import sys

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# ── Les 7 modes de présence ───────────────────────────────────────────
#
# Ce que fait Luca's doit se lire sur son visage. Les sept états
# couvrent tout ce qu'elle peut être en train de faire.
#
# ⚠️ À ne pas confondre avec les 8 « modes AURA » d'IDEAS.md, qui sont
# des contextes d'activité de Cyril (Working, Gaming, Meeting…) prévus
# en S5. Ici il s'agit de l'état de Luca's elle-même.
#
# Passé de 5 à 7 le 08/08/2026 (Brique 4 du noyau minimal) — deux ajouts,
# tranchés explicitement par Cyril avant ce chantier :
#   - THINKING_DEEP : réfléchit plus longtemps, escalade cloud (Brique 1,
#     core/lucas_core.py::ask()) — distinct de THINKING (réflexion locale).
#   - OBSERVING : observation SOUTENUE, par opposition à WATCHING qui
#     reste une capture PONCTUELLE (balayage actif, point témoin
#     clignotant). IDLE ne compte pas parmi les « 6 états » du brief —
#     c'est le repos implicite, pas une activité.

IDLE = "IDLE"                    # au repos, respiration lente
THINKING = "THINKING"            # génère une réponse (local)
THINKING_DEEP = "THINKING_DEEP"  # génère une réponse (escalade cloud)
SPEAKING = "SPEAKING"            # parle (TTS)
WATCHING = "WATCHING"            # regarde l'écran, capture ponctuelle (VLM)
OBSERVING = "OBSERVING"          # observe l'écran, présence soutenue
LISTENING = "LISTENING"          # attentive : Cyril s'adresse à elle

PRESENCE_STATES = (IDLE, LISTENING, WATCHING, OBSERVING, SPEAKING, THINKING, THINKING_DEEP)

# LISTENING ne veut pas dire « micro ouvert » : il signifie que Cyril est
# en train de s'adresser à Luca's. Il est déclenché aujourd'hui par la
# saisie clavier (ui.main_window._on_typing) — donc les cinq modes sont
# bel et bien atteignables. Le micro viendra s'y ajouter avec le pont
# mobile (IDEAS.md #69), sans changer le sens de l'état.

# Ambre plutôt que cyan pour WATCHING, et c'est un choix de sécurité :
# l'avatar sert de témoin, comme la LED d'une webcam. Quand Luca's
# regarde l'écran de Cyril, ça doit sauter aux yeux et non se fondre
# dans l'ambiance habituelle de l'interface.
WATCHING_COLOR = QColor(255, 170, 0)
# Ambre plus sourd pour OBSERVING : même famille (contour = témoin de
# lecture d'écran), mais une présence soutenue ne doit pas cligner comme
# une alerte — sinon les deux se confondraient.
OBSERVING_COLOR = QColor(200, 140, 60)
# Contour de témoin par état — WATCHING et OBSERVING seulement, les
# autres restent cyan (border_color() ci-dessous).
WITNESS_COLORS = {WATCHING: WATCHING_COLOR, OBSERVING: OBSERVING_COLOR}

# ── Esthétique : inspiration DeepMind Project Astra ───────────────────
#
# Ajoutée le 01/08/2026 (VISION_LONG_TERME.md, Pilier 1 + addendum).
# Ce qu'on en retient concrètement, par opposition au rendu précédent :
#
#   • halo en couches douces plutôt qu'un seul dégradé plat
#   • dégradés à plusieurs teintes qui se fondent, pas deux arrêts secs
#   • respiration permanente — la forme n'est jamais parfaitement figée
#   • mouvement présent même au repos, jamais totalement immobile
#
# Le visage est conservé : HER et Desktop Pal restent des inspirations
# documentées, et des yeux qui suivent le curseur donnent une présence
# qu'une sphère abstraite n'a pas. Astra apporte la matière, pas le
# remplacement du personnage.

# Palette par état : arrêts (position, R, G, B, alpha) du halo.
# Trois teintes minimum, pour que le dégradé respire au lieu de trancher.
HALO_PALETTES = {
    IDLE: [(0.0, 0, 212, 255, 70), (0.55, 90, 120, 240, 30), (1.0, 124, 58, 237, 0)],
    THINKING: [(0.0, 160, 90, 255, 140), (0.5, 124, 58, 237, 70), (1.0, 70, 20, 160, 0)],
    # Plus intense que THINKING (140/90/40 vs 160/124/70) : la profondeur
    # de couleur signale l'escalade cloud, pas seulement le libellé.
    THINKING_DEEP: [(0.0, 140, 20, 255, 170), (0.5, 90, 10, 200, 90), (1.0, 40, 5, 120, 0)],
    SPEAKING: [(0.0, 0, 230, 255, 110), (0.5, 60, 160, 255, 60), (1.0, 124, 58, 237, 0)],
    WATCHING: [(0.0, 255, 200, 60, 170), (0.45, 255, 150, 0, 90), (1.0, 200, 90, 0, 0)],
    # Ambre plus sourd et moins opaque que WATCHING : une présence
    # soutenue, pas un signal ponctuel.
    OBSERVING: [(0.0, 220, 160, 80, 140), (0.45, 200, 120, 40, 70), (1.0, 150, 70, 10, 0)],
    LISTENING: [(0.0, 0, 255, 220, 130), (0.5, 0, 200, 255, 60), (1.0, 0, 120, 200, 0)],
}

# Amplitude de la respiration, en pixels de rayon.
BREATH_AMPLITUDE = 2.2

# Durée d'un fondu entre deux modes, en frames à 20 fps.
# Ramené de 8 à 5 frames (400 → 250 ms) après essai de Cyril : 400 ms
# traînaient. Assez pour adoucir l'amorce, assez court pour que le
# témoin WATCHING reste franc. Un basculement instantané, à l'inverse,
# passe pour un défaut d'affichage.
TRANSITION_FRAMES = 5

# Ce que Luca's affiche sous son visage. Les noms d'état sont techniques ;
# Cyril doit lire ce qu'elle fait, pas une constante.
STATE_LABELS = {
    IDLE: "prête",
    THINKING: "réfléchit",
    THINKING_DEEP: "réfléchit plus",
    SPEAKING: "parle",
    WATCHING: "regarde",
    OBSERVING: "observe",
    LISTENING: "écoute",
}


class AvatarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(140, 140)
        # WA_TransparentBackground n'existe pas dans Qt : l'attribut correct
        # est WA_TranslucentBackground. Ce bug empêchait l'avatar — donc
        # toute l'interface — de démarrer.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.state = IDLE
        self.mouth_open = 0.0
        self.glow_intensity = 0.5
        self.glow_direction = 1
        self.eye_blink = False
        self.blink_timer = 0
        self.particles = []
        self.mouse_pos = QPointF(70, 70)
        # Position de la ligne de balayage du mode WATCHING, en pixels
        # depuis le haut du visage.
        self.scan_offset = 0.0
        # Point témoin clignotant et balayage du regard, tous deux propres
        # au mode WATCHING. Le halo ambre seul ne se remarquait pas assez
        # quand l'avatar est en périphérie du champ de vision.
        self.watch_pulse = 0.0
        self.gaze_phase = 0.0
        # Phase de respiration : avance en continu, quel que soit l'état.
        # Rien ne doit jamais être parfaitement immobile (inspiration
        # Astra) — un avatar figé donne l'impression d'un programme planté.
        self.breath_phase = 0.0
        # Fondu entre deux modes : l'état d'où l'on vient, et l'avancement
        # de 0 à 1. À 1, la transition est terminée.
        self.previous_state = IDLE
        self.transition = 1.0

        # Timer animation globale (20fps réel — voir intervalle ci-dessous)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.start(50)  # 20fps

        # Timer clignement — intervalle non périodique, voir trigger_blink().
        # Premier armement à une valeur tirée elle aussi : sans ça, seul le
        # tout premier clignement suivrait l'ancien rythme fixe.
        self.blink_timer_obj = QTimer(self)
        self.blink_timer_obj.timeout.connect(self.trigger_blink)
        self.blink_timer_obj.start(random.randint(2000, 6000))

        self.setMouseTracking(True)

    def set_state(self, state):
        """
        Change l'état affiché.

        Un état inconnu retombe sur IDLE plutôt que d'être accepté tel
        quel : sans ça, paintEvent dessinait un dégradé sans couleur,
        et l'avatar disparaissait à moitié sans que rien ne l'explique.
        """
        if state not in PRESENCE_STATES:
            state = IDLE
        if state != self.state:
            # On mémorise d'où l'on vient pour fondre les deux palettes.
            self.previous_state = self.state
            self.transition = 0.0
        self.state = state
        self.update()

    def update_mouth(self, open_ratio):
        self.mouth_open = max(0.0, min(1.0, open_ratio))
        self.update()

    def trigger_blink(self):
        """
        Clignement — jamais périodique (Brique 4, 08/08/2026). Un clignement
        au rythme parfaitement régulier (l'ancien `start(3000)` fixe) se lit
        comme un tic mécanique ; un intervalle tiré à chaque déclenchement
        (2-6 s) casse la régularité sans jamais s'arrêter de cligner.
        """
        if self.state == IDLE:
            self.eye_blink = True
            self.blink_timer = 3
            QTimer.singleShot(150, self.end_blink)
        self.blink_timer_obj.start(random.randint(2000, 6000))

    def end_blink(self):
        self.eye_blink = False
        self.update()

    def body_radius(self) -> float:
        """Rayon du visage, respiration comprise."""
        return 45.0 + math.sin(self.breath_phase) * BREATH_AMPLITUDE

    @staticmethod
    def _ease(t: float) -> float:
        """
        Adoucit un fondu linéaire (ease-in-out).

        Une interpolation brute démarre et s'arrête net ; l'œil le
        perçoit comme une saccade même sur 400 ms.
        """
        return t * t * (3.0 - 2.0 * t)

    def current_palette(self) -> list[tuple]:
        """
        Palette du halo, fondue entre l'état précédent et l'actuel.

        Un état inconnu retombe sur IDLE : sans arrêt de couleur, Qt
        dessine un halo transparent et l'avatar semble amputé.
        """
        target = HALO_PALETTES.get(self.state, HALO_PALETTES[IDLE])
        if self.transition >= 1.0:
            return target

        source = HALO_PALETTES.get(self.previous_state, HALO_PALETTES[IDLE])
        t = self._ease(self.transition)
        return [
            tuple(a + (b - a) * t for a, b in zip(stop_from, stop_to))
            for stop_from, stop_to in zip(source, target)
        ]

    def border_color(self) -> QColor:
        """Contour du visage, fondu entre l'ancien et le nouveau mode."""
        cyan = QColor(0, 212, 255)
        target = WITNESS_COLORS.get(self.state, cyan)
        if self.transition >= 1.0:
            return QColor(target.red(), target.green(), target.blue(), 150)

        source = WITNESS_COLORS.get(self.previous_state, cyan)
        t = self._ease(self.transition)
        return QColor(
            int(source.red() + (target.red() - source.red()) * t),
            int(source.green() + (target.green() - source.green()) * t),
            int(source.blue() + (target.blue() - source.blue()) * t),
            150,
        )

    def _halo_gradient(self, center: QPointF, radius: float) -> QRadialGradient:
        """Dégradé du halo pour l'instant courant, fondu compris."""
        gradient = QRadialGradient(center, radius)
        for position, r, g, b, alpha in self.current_palette():
            gradient.setColorAt(
                min(1.0, max(0.0, position)),
                QColor(int(r), int(g), int(b), int(alpha)),
            )
        return gradient

    def update_animation(self):
        # La respiration avance toujours, y compris dans les états qui ne
        # touchent pas au reste.
        self.breath_phase = (self.breath_phase + 0.08) % (2 * math.pi)

        # Avancement du fondu entre deux modes.
        if self.transition < 1.0:
            self.transition = min(1.0, self.transition + 1.0 / TRANSITION_FRAMES)

        # Glow pulsation
        if self.state == IDLE:
            self.glow_intensity += 0.02 * self.glow_direction
            if self.glow_intensity >= 0.8:
                self.glow_direction = -1
            elif self.glow_intensity <= 0.3:
                self.glow_direction = 1
        elif self.state == LISTENING:
            self.glow_intensity = 0.9 + 0.1 * random.random()
        elif self.state == THINKING:
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
        elif self.state == THINKING_DEEP:
            # Même mécanique que THINKING, plus soutenue : glow plus haut,
            # particules plus denses et qui durent plus longtemps — la
            # réflexion visible dure plus longtemps qu'un aller-retour
            # local (escalade cloud, core/lucas_core.py::ask()).
            self.glow_intensity = 0.8 + 0.2 * random.random()
            if random.random() > 0.5:
                self.particles.append({
                    'x': 70 + random.randint(-40, 40),
                    'y': 70 + random.randint(-20, 20),
                    'size': random.randint(2, 6),
                    'life': 1.0,
                    'speed': random.uniform(0.5, 2.2)
                })
            for p in self.particles:
                p['y'] -= p['speed']
                p['life'] -= 0.04
            self.particles = [p for p in self.particles if p['life'] > 0]
        elif self.state == SPEAKING:
            self.mouth_open = 0.3 + 0.4 * abs(random.random() - 0.5) * 2
            self.glow_intensity = 0.6
        elif self.state == WATCHING:
            # Halo soutenu et stable : Luca's est concentrée sur l'écran,
            # pas en train de réfléchir dans le vide.
            self.glow_intensity = 0.85
            # Balayage descendant qui reboucle — le signe visible que la
            # capture est en cours.
            self.scan_offset = (self.scan_offset + 2.5) % 90
            # Point témoin : clignotement franc, comme une LED
            # d'enregistrement. C'est lui qu'on repère du coin de l'œil.
            self.watch_pulse = (self.watch_pulse + 0.16) % (2 * math.pi)
            # Le regard balaie au lieu de fixer : une pupille immobile
            # donne un air absent, pas curieux.
            self.gaze_phase = (self.gaze_phase + 0.09) % (2 * math.pi)
        elif self.state == OBSERVING:
            # Présence soutenue, PAS un signal ponctuel : contrairement à
            # WATCHING, ni balayage actif (scan_offset) ni point témoin
            # clignotant (watch_pulse) — seul le regard dérive, lentement.
            self.glow_intensity = 0.65
            self.gaze_phase = (self.gaze_phase + 0.03) % (2 * math.pi)

        self.update()

    def mouseMoveEvent(self, event):
        self.mouse_pos = QPointF(event.pos())
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center = QPointF(70, 70)
        radius = self.body_radius()

        # Halo en trois couches concentriques plutôt qu'un dégradé unique :
        # la lumière se diffuse au lieu de s'arrêter net (esthétique Astra).
        painter.setPen(Qt.PenStyle.NoPen)
        base_glow = 55 + self.glow_intensity * 10
        for scale, opacity in ((1.25, 0.35), (1.10, 0.6), (1.0, 1.0)):
            layer_radius = base_glow * scale
            painter.setOpacity(opacity)
            painter.setBrush(QBrush(self._halo_gradient(center, layer_radius)))
            painter.drawEllipse(center, layer_radius, layer_radius)
        painter.setOpacity(1.0)

        # Corps principal
        body_gradient = QRadialGradient(center, radius)
        body_gradient.setColorAt(0, QColor(20, 20, 40))
        body_gradient.setColorAt(0.7, QColor(10, 10, 25))
        body_gradient.setColorAt(1, QColor(0, 212, 255, 100))

        painter.setBrush(QBrush(body_gradient))
        # Contour ambre en mode WATCHING : le visage entier change de
        # couleur, on ne peut pas le manquer du coin de l'œil. Le contour
        # suit le même fondu que le halo, sinon il claquerait tout seul
        # pendant que le reste se fond doucement.
        painter.setPen(QPen(self.border_color(), 2))
        painter.drawEllipse(center, radius, radius)

        # Point témoin de capture — la LED d'enregistrement. Le halo ambre
        # seul ne se remarquait pas assez quand l'avatar est en périphérie
        # du champ de vision ; un point qui clignote, si.
        if self.state == WATCHING:
            pulse = (math.sin(self.watch_pulse) + 1.0) / 2.0
            dot_alpha = int(90 + 165 * pulse)
            dot_radius = 4.0 + 1.5 * pulse
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(255, 90, 0, dot_alpha)))
            painter.drawEllipse(QPointF(107, 36), dot_radius, dot_radius)

        # Yeux
        if not self.eye_blink:
            if self.state in (WATCHING, OBSERVING):
                # Le regard balaie l'écran au lieu de suivre la souris.
                # Un regard fixe donnait un air absent ; ce parcours
                # lent, plus large que haut, se lit comme de la curiosité.
                # Le curseur reste ignoré : elle lit l'écran, pas la main.
                dx = math.sin(self.gaze_phase) * 7.0
                dy = math.sin(self.gaze_phase * 0.4) * 2.5
                dist = 0.0
            else:
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
            painter.setPen(Qt.PenStyle.NoPen)
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

        # Ligne de balayage (état WATCHING)
        if self.state == WATCHING:
            scan_y = 28 + self.scan_offset
            painter.setPen(QPen(QColor(WATCHING_COLOR.red(), WATCHING_COLOR.green(), 0, 180), 2))
            # Largeur suivant la courbure du visage, pour que la ligne
            # reste à l'intérieur du cercle. Le rayon respire depuis la
            # V3 : utiliser 45 en dur ferait déborder ou rentrer la ligne
            # au rythme de la respiration.
            half = max(0.0, (radius**2 - (scan_y - 70.0) ** 2)) ** 0.5
            painter.drawLine(int(70 - half), int(scan_y), int(70 + half), int(scan_y))

        # Particules (états THINKING / THINKING_DEEP)
        if self.state in (THINKING, THINKING_DEEP):
            for p in self.particles:
                alpha = int(p['life'] * 255)
                painter.setBrush(QBrush(QColor(0, 212, 255, alpha)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(p['x'], p['y']), p['size'], p['size'])

        # Label état
        painter.setPen(QPen(QColor(0, 212, 255, 150), 1))
        painter.setFont(QFont("Consolas", 7))
        # Libellé lisible plutôt que le nom de la constante : Cyril doit
        # lire ce que Luca's fait, pas « WATCHING ».
        painter.drawText(
            40, 130, 60, 15, Qt.AlignmentFlag.AlignCenter, STATE_LABELS.get(self.state, "")
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = QWidget()
    window.setWindowTitle("Test Avatar Luca's")
    window.setFixedSize(300, 400)
    window.setStyleSheet("background-color: #0a0a0a;")

    layout = QVBoxLayout()

    avatar = AvatarWidget()
    layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignCenter)

    btn_layout = QHBoxLayout()

    for state in [
        "IDLE", "LISTENING", "WATCHING", "OBSERVING",
        "SPEAKING", "THINKING", "THINKING_DEEP",
    ]:
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
