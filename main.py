# main.py — point d'entrée. Ne fait QUE démarrer l'application.
# Toute la logique est dans core/ et ui/.

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

# Instrumentation temporaire (03/08/2026) — diagnostic d'un comportement KO
# côté vision/intent signalé par Cyril. Un logger par module traversé
# (ui.main_window, core.router, core.intent, core.lucas_core), pour situer
# précisément où le comportement observé diverge de celui attendu. À
# retirer une fois le bug réel diagnostiqué et corrigé, pas une
# instrumentation permanente.
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    filename="logs/intent_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] %(message)s",
)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()