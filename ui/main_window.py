import sys
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt

class MainWindow:
    def __init__(self):
        self.window = self.create_window()

    def create_window(self):
        window = QWidget()
        window.setStyleSheet("""
            background-color: #0a0a0a;
            border-radius: 15px;
            box-shadow: 0 0 10px rgba(0, 213, 255, 0.5);
        """)
        return window

    def show(self):
        self.window.show()

if __name__ == '__main__':
    main_window = MainWindow()
    main_window.show()
