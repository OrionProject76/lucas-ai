# main.py — point d'entrée. Ne fait QUE démarrer l'application.
# Toute la logique est dans core/ et ui/.

import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()