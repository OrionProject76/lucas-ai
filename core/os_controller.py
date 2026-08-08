# core/os_controller.py — actions système sur liste blanche stricte
#
# Fonctions codées à la main, jamais un script généré par un LLM (CLAUDE.md
# règle non négociable). Brique 2 du noyau minimal, 08/08/2026 — voir
# ROADMAP.md.
#
# Lancer une application reste dans modules/automation_manager.py (liste
# blanche déjà là, séparée) — ce module ne le redéfinit pas. Il couvre ce
# qui manquait : organiser des fichiers dans des dossiers autorisés,
# capturer l'écran, régler le volume, lire/écrire le presse-papiers.

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from config import ALLOWED_DIRECTORIES

if TYPE_CHECKING:
    from memory.memory_manager import MemoryManager


class PathNotAllowed(Exception):
    """Chemin hors des répertoires autorisés — jamais une exception silencieuse."""


class DestructiveActionRefused(Exception):
    """Écrasement d'un fichier existant refusé — confirmation absente ou négative."""


def _resolve_and_check(path: str, allowed_directories: list[str]) -> Path:
    """
    Résout le chemin (symlinks compris) et vérifie qu'il est CONTENU dans un
    des répertoires autorisés.

    Jamais une comparaison de préfixe de chaîne : "C:\\Documents2" commence
    comme "C:\\Documents" sans y être contenu, et un chemin non résolu se
    contourne par "..". `Path.resolve()` élimine les deux.
    """
    resolved = Path(path).resolve()
    for allowed in allowed_directories:
        allowed_resolved = Path(allowed).resolve()
        if resolved == allowed_resolved or allowed_resolved in resolved.parents:
            return resolved
    raise PathNotAllowed(f"Chemin hors des répertoires autorisés : {path}")


def _get_volume_interface():
    """
    Interface COM du volume du périphérique de sortie principal.

    Isolée dans sa propre fonction pour rester mockable en test sans tirer
    pycaw/comtypes — aucun test ne doit dépendre du matériel audio réel de
    la machine qui exécute la suite.
    """
    from pycaw.pycaw import AudioUtilities

    return AudioUtilities.GetSpeakers().EndpointVolume


class OSController:
    """
    Actions système sous liste blanche stricte.

    `memory` : injecté (comme `log_event` ailleurs dans le projet) pour
    journaliser chaque action dans `action_log` (table déjà utilisée par
    core/decision_engine.py) — sans instance, aucune journalisation n'a
    lieu, jamais une exception silencieuse.

    `confirm_destructive` : callable (message: str) -> bool, consulté avant
    tout écrasement de fichier existant. Sans confirmation injectée : refus
    par défaut — même garde que `DecisionEngine.confirm` (core/
    decision_engine.py) : un mécanisme indisponible ne doit jamais avoir
    pour effet d'AUTORISER une action destructrice.
    """

    def __init__(
        self,
        memory: MemoryManager | None = None,
        confirm_destructive: Callable[[str], bool] | None = None,
        allowed_directories: list[str] | None = None,
    ) -> None:
        self.memory = memory
        self.confirm_destructive = confirm_destructive
        self.allowed_directories = (
            list(allowed_directories) if allowed_directories is not None else list(ALLOWED_DIRECTORIES)
        )

    def _check(self, path: str) -> Path:
        return _resolve_and_check(path, self.allowed_directories)

    def _confirm(self, message: str) -> bool:
        return self.confirm_destructive is not None and self.confirm_destructive(message)

    def move_file(self, source: str, destination: str) -> str:
        """Déplace un fichier d'un dossier autorisé vers un autre. Écrasement -> confirmation."""
        source_path = self._check(source)
        dest_path = self._check(destination)
        params = {"source": source, "destination": destination}

        if not source_path.exists():
            self._log_action("move_file", params, "denied")
            raise FileNotFoundError(f"Fichier source introuvable : {source}")

        if dest_path.exists() and not self._confirm(
            f"Écraser « {dest_path} » avec « {source_path.name} » ?"
        ):
            self._log_action("move_file", params, "denied")
            raise DestructiveActionRefused(f"Écrasement refusé : {dest_path}")

        shutil.move(str(source_path), str(dest_path))
        self._log_action("move_file", params, "executed")
        return f"« {source_path.name} » déplacé vers « {dest_path} »"

    def rename_file(self, path: str, new_name: str) -> str:
        """Renomme un fichier au sein d'un dossier autorisé. Écrasement -> confirmation."""
        source_path = self._check(path)
        dest_path = self._check(str(source_path.parent / new_name))
        params = {"path": path, "new_name": new_name}

        if not source_path.exists():
            self._log_action("rename_file", params, "denied")
            raise FileNotFoundError(f"Fichier introuvable : {path}")

        if dest_path.exists() and not self._confirm(
            f"Écraser « {dest_path} » en renommant « {source_path.name} » ?"
        ):
            self._log_action("rename_file", params, "denied")
            raise DestructiveActionRefused(f"Écrasement refusé : {dest_path}")

        source_path.rename(dest_path)
        self._log_action("rename_file", params, "executed")
        return f"« {source_path.name} » renommé en « {new_name} »"

    def take_screenshot(self, output_path: str | None = None) -> str:
        """Capture l'écran — délègue à VisionManager, jamais un second chemin de capture."""
        from modules.vision_manager import VisionManager

        result_path = VisionManager().capture_screen(output_path)
        self._log_action("take_screenshot", {"output_path": output_path}, "executed")
        return result_path

    def get_volume(self) -> int:
        """Volume principal actuel, 0-100. Lecture seule : jamais journalisé (ActionCategory.READ)."""
        return round(_get_volume_interface().GetMasterVolumeLevelScalar() * 100)

    def set_volume(self, level: int) -> str:
        """Règle le volume principal, 0-100 (borné, jamais hors plage)."""
        clamped = max(0, min(100, level))
        _get_volume_interface().SetMasterVolumeLevelScalar(clamped / 100, None)
        self._log_action("set_volume", {"level": clamped}, "executed")
        return f"Volume réglé à {clamped}%"

    def read_clipboard(self) -> str:
        """
        Lit le presse-papiers. Lecture seule : jamais journalisé.

        pyperclip plutôt que QApplication.clipboard() : ce module doit
        fonctionner aussi bien depuis l'UI PySide6 que depuis le pont
        mobile FastAPI (aucune boucle Qt vivante dans ce second cas).
        """
        import pyperclip

        return pyperclip.paste()

    def write_clipboard(self, text: str) -> str:
        """Écrit dans le presse-papiers."""
        import pyperclip

        pyperclip.copy(text)
        self._log_action("write_clipboard", {"length": len(text)}, "executed")
        return "Presse-papiers mis à jour"

    def _log_action(self, action: str, params: dict, result: str) -> None:
        if self.memory is not None:
            self.memory.save_action(action, source="os_controller", result=result, params=params)
