# demos/demo_vision.py — démonstration manuelle de la vision
#
# Ancien test_vision.py : ce n'était pas un test mais une démo qui
# capture réellement l'écran et interroge le VLM. Les vrais tests de
# VisionManager sont dans test_modules.py.
#
# Usage : python demos/demo_vision.py  (Ollama doit tourner, llava installé)

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.vision_manager import VisionManager


def main() -> None:
    vm = VisionManager()

    print("Capture d'écran...")
    screenshot_path = vm.capture_screen()
    print(f"Capture sauvegardée : {screenshot_path}")

    print("\nAnalyse par le VLM local...")
    print(f"Luca's voit : {vm.analyze_image(screenshot_path)}")


if __name__ == "__main__":
    main()
