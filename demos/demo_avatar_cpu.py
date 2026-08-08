# demos/demo_avatar_cpu.py — mesurer le coût CPU réel de l'avatar en IDLE
#
# Critère V7 du brief du 08/08/2026 (Brique 4) : < 2% CPU en idle, 0 VRAM
# dédiée (QPainter pur, aucun rendu GPU). Jamais mesuré jusqu'ici — ce
# script comble ça, plutôt que de supposer que le budget tient.
#
# Mesure approximative (process entier, pas isolé du reste de l'UI) —
# suffisante pour ce critère, qui n'a jamais eu d'instrumentation avant
# aujourd'hui. Usage : python demos/demo_avatar_cpu.py

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psutil
from PySide6.QtWidgets import QApplication

from ui.avatar_widget import IDLE, AvatarWidget


def main() -> None:
    app = QApplication(sys.argv)
    avatar = AvatarWidget()
    avatar.set_state(IDLE)
    avatar.show()

    process = psutil.Process()
    # Premier appel : amorce la mesure (cpu_percent nécessite un intervalle
    # de référence, la première valeur est toujours 0.0 sinon).
    process.cpu_percent(interval=None)

    duration_seconds = 15
    print(f"Avatar en IDLE, mesure sur {duration_seconds} s...")
    start = time.monotonic()
    while time.monotonic() - start < duration_seconds:
        app.processEvents()
        time.sleep(0.01)

    percent = process.cpu_percent(interval=None)
    print(f"CPU process (avatar IDLE, {duration_seconds} s) : {percent:.1f} %")
    # Pas d'emoji dans cette sortie : la console Windows par défaut
    # (cp1252) plante sur UnicodeEncodeError, trouvé en exécutant ce
    # script réellement le 08/08/2026.
    if percent >= 2.0:
        print("AU-DESSUS du budget de 2 % annonce au brief -- a signaler a Cyril.")
    else:
        print("OK -- sous le budget de 2 %.")


if __name__ == "__main__":
    main()
