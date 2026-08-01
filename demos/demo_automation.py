# demos/demo_automation.py — démonstration manuelle de la liste blanche
#
# Ancien test_automation.py : ce n'était pas un test mais une démo qui
# ouvre RÉELLEMENT Chrome et la calculatrice. Les vrais tests sont dans
# test_automation.py, où subprocess est mocké.
#
# Usage : python demos/demo_automation.py

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.automation_manager import AutomationManager


def main() -> None:
    am = AutomationManager(log_event=lambda t, d="": print(f"  [event] {t} : {d}"))

    print("Applications autorisées :", ", ".join(am.list_allowed()))

    for app in ("calculatrice", "virus"):
        print(f"\nOuverture de « {app} »...")
        print("  ->", am.open_app(app))
        time.sleep(1)


if __name__ == "__main__":
    main()
