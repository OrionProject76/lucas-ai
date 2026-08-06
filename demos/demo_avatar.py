# demos/demo_avatar.py — juger l'avatar à l'œil
#
# Les tests prouvent que les cinq modes diffèrent, que la respiration
# avance et que les fondus se terminent. Ils ne disent pas si c'est beau,
# si le rythme est bon, si le témoin ambre est assez franc. Seul Cyril
# peut en juger — cette démo est là pour ça.
#
# Aucune dépendance : ni Ollama, ni Piper, ni base de données. Elle
# n'affiche que l'avatar.
#
# Usage : python demos/demo_avatar.py

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.avatar_widget import (
    PRESENCE_STATES,
    STATE_LABELS,
    TRANSITION_FRAMES,
    AvatarWidget,
)

BUTTON_STYLE = """
QPushButton {
    background-color: #14141A;
    color: #00D4FF;
    border: 1px solid #2A2C38;
    border-radius: 8px;
    padding: 10px;
    font-family: Consolas;
}
QPushButton:hover { background-color: #00D4FF; color: #0D0D12; }
"""


class AvatarDemo(QWidget):
    """Fenêtre de contrôle : un bouton par mode, plus un cycle automatique."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Luca's — les 5 modes de présence")
        self.setFixedSize(340, 480)
        self.setStyleSheet("background-color: #0A0A0F; color: #E8EAED;")

        layout = QVBoxLayout()
        layout.setSpacing(14)

        self.avatar = AvatarWidget()
        layout.addWidget(self.avatar, alignment=Qt.AlignmentFlag.AlignCenter)

        self.caption = QLabel("")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption.setStyleSheet("color: #6B6F7B; font-size: 12px;")
        layout.addWidget(self.caption)

        grid = QGridLayout()
        for index, state in enumerate(PRESENCE_STATES):
            button = QPushButton(f"{state}\n« {STATE_LABELS[state]} »")
            button.setStyleSheet(BUTTON_STYLE)
            button.clicked.connect(lambda _checked, s=state: self.show_state(s))
            grid.addWidget(button, index // 2, index % 2)
        layout.addLayout(grid)

        cycle = QPushButton("▶  Cycle automatique — regarder les fondus")
        cycle.setStyleSheet(BUTTON_STYLE)
        cycle.clicked.connect(self.toggle_cycle)
        layout.addWidget(cycle)

        hint = QLabel(
            "WATCHING est le témoin de capture d'écran :\n"
            "il doit se remarquer sans qu'on le cherche.\n"
            f"Fondu entre deux modes : {TRANSITION_FRAMES} frames (~400 ms)."
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #6B6F7B; font-size: 11px;")
        layout.addWidget(hint)

        self.setLayout(layout)

        # Cycle : 2,5 s par mode, assez pour voir le fondu puis le régime
        # établi de chacun.
        self.cycle_timer = QTimer(self)
        self.cycle_timer.timeout.connect(self.next_state)
        self.cycle_index = 0

        self.show_state(PRESENCE_STATES[0])

    def show_state(self, state: str) -> None:
        self.avatar.set_state(state)
        self.caption.setText(f"{state} — « {STATE_LABELS[state]} »")

    def next_state(self) -> None:
        self.cycle_index = (self.cycle_index + 1) % len(PRESENCE_STATES)
        self.show_state(PRESENCE_STATES[self.cycle_index])

    def toggle_cycle(self) -> None:
        if self.cycle_timer.isActive():
            self.cycle_timer.stop()
        else:
            self.cycle_timer.start(2500)


def main() -> None:
    app = QApplication(sys.argv)
    window = AvatarDemo()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
