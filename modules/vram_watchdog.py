# modules/vram_watchdog.py — surveille la VRAM libre, arrête l'avatar
# Godot (Lucas3D.exe) quand la marge devient trop faible.
#
# Prérequis bloquant avant toute nouvelle brique visuelle Godot (mesh
# définitif, shader, HUD) — voir cowork_workspace/REFERENCE_VISUELLE_AVATAR.md
# §1 bis, conflit n°2. Godot ne doit jamais partir du principe qu'il a
# de la place : gpt-oss:20b seul, mesuré le 07/08/2026, laisse déjà
# aussi peu que ~550 Mo libres.
#
# Ce module ne relance PAS Godot automatiquement quand la VRAM revient
# au-dessus du seuil — il se contente de lever le blocage (log
# `vram_watchdog_restore`) et de ne plus l'arrêter. Relancer un
# compagnon de bureau tout seul, sans que Cyril soit devant l'écran,
# n'est pas dans le périmètre de cette brique (CLAUDE.md, "rien de
# visuel ne se construit sans Cyril devant l'écran").
#
# Méthode d'arrêt : taskkill /F /IM Lucas3D.exe, la même que
# demos/arreter_lucas3d.bat, déjà testée en conditions réelles
# (ROADMAP.md §5.67). Pas de P/Invoke, pas de contrôle de fenêtre —
# seulement un arrêt de process (CLAUDE.md, précision du 04/08/2026).

import subprocess
import threading
from pathlib import Path

from config import VRAM_WATCHDOG_POLL_SECONDS, VRAM_WATCHDOG_THRESHOLD_MB
from memory.memory_manager import save_event_from_any_thread

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LUCAS3D_IMAGE_NAME = "Lucas3D.exe"


def get_free_vram_mb() -> float | None:
    """VRAM libre en Mo, None si illisible (pas de GPU, pilote absent).

    Reprend GPUtil, déjà utilisé par core/world_model.py pour la jauge
    GPU du HUD — même dépendance, pas une nouvelle.
    """
    try:
        import GPUtil

        gpus = GPUtil.getGPUs()
        return round(gpus[0].memoryFree, 1) if gpus else None
    except Exception:  # noqa: BLE001 — pilote absent, machine sans GPU
        return None


def is_lucas3d_running() -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {LUCAS3D_IMAGE_NAME}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return LUCAS3D_IMAGE_NAME.lower() in result.stdout.lower()
    except Exception:  # noqa: BLE001 — tasklist indisponible : on ne sait
        # pas, donc on n'agit pas plutôt que de supposer.
        return False


def stop_lucas3d() -> bool:
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", LUCAS3D_IMAGE_NAME],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return True
    except Exception:  # noqa: BLE001 — voir is_lucas3d_running
        return False


class VramWatchdog:
    """Poll la VRAM libre en tâche de fond, arrête Godot sous le seuil."""

    def __init__(
        self,
        threshold_mb: int = VRAM_WATCHDOG_THRESHOLD_MB,
        poll_seconds: float = VRAM_WATCHDOG_POLL_SECONDS,
    ) -> None:
        self.threshold_mb = threshold_mb
        self.poll_seconds = poll_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        # Vrai entre un arrêt déclenché par ce watchdog et le retour
        # au-dessus du seuil — évite de réémettre l'événement de
        # bascule à chaque passage tant que la cause n'a pas changé.
        self.in_fallback = False

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.poll_seconds + 5)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            self.check_once()
            self._stop_event.wait(self.poll_seconds)

    def check_once(self) -> None:
        """Un seul cycle de mesure + décision — exposé pour les tests."""
        free_mb = get_free_vram_mb()
        if free_mb is None:
            return  # rien à décider sans mesure fiable

        if free_mb < self.threshold_mb and not self.in_fallback:
            if is_lucas3d_running() and stop_lucas3d():
                self.in_fallback = True
                save_event_from_any_thread(
                    "vram_watchdog_fallback",
                    f"VRAM libre {free_mb:.0f} Mo < seuil {self.threshold_mb} Mo "
                    "— Lucas3D.exe arrêté, repli sur l'avatar 2D",
                )
        elif free_mb >= self.threshold_mb and self.in_fallback:
            self.in_fallback = False
            save_event_from_any_thread(
                "vram_watchdog_restore",
                f"VRAM libre {free_mb:.0f} Mo >= seuil {self.threshold_mb} Mo "
                "— retour à l'avatar Godot possible (non automatique)",
            )


if __name__ == "__main__":
    import time

    print(f"Watchdog VRAM — seuil {VRAM_WATCHDOG_THRESHOLD_MB} Mo, "
          f"poll {VRAM_WATCHDOG_POLL_SECONDS}s. Ctrl+C pour arrêter.")
    watchdog = VramWatchdog()
    watchdog.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watchdog.stop()
