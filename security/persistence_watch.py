# security/persistence_watch.py — points de démarrage automatique
#
# ── Pourquoi ce module s'appelle « persistance » et non « keylogger » ──
#
# ROADMAP listait « suivi des hooks clavier » comme palier suivant. Ce
# n'est PAS observable depuis Python de façon portable : énumérer les
# hooks SetWindowsHookEx demande des appels natifs Win32 que psutil
# n'expose pas, et un keylogger correct ne se distingue d'aucun autre
# processus par ses attributs visibles.
#
# Écrire un module nommé « détecteur de keylogger » qui ne détecte rien
# serait pire qu'inutile : il donnerait une fausse assurance, exactement
# ce que le principe de VISION_LONG_TERME.md §4.1 cherche à éviter.
#
# Ce qui EST observable, et qui vise le même adversaire : un keylogger
# doit survivre au redémarrage. Il s'inscrit donc dans les points de
# persistance de Windows — clés Run du registre, dossier Démarrage. Ces
# emplacements se lisent, et une entrée pointant vers un répertoire
# temporaire est un signal fort et peu bruyant.
#
# Observation seule : ce module LIT le registre, il n'y écrit jamais.

import os
from collections.abc import Callable
from pathlib import Path

from security.guardian import VOLATILE_DIRECTORIES
from security.types import CRITICAL, INFO, WARNING, Finding

# Emplacements de démarrage automatique, par ruche et sous-clé.
# RunOnce est inclus : c'est le vecteur classique d'une charge qui
# s'installe au premier redémarrage puis efface sa trace.
AUTOSTART_KEYS = [
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run"),
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
    ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Run"),
    ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
]

STARTUP_FOLDER_KEY = "Startup"


def _read_registry_autostarts() -> list[tuple[str, str, str]]:
    """
    Entrées de démarrage du registre : (source, nom, commande).

    Retourne une liste vide hors Windows ou si le registre est illisible
    — un capteur indisponible ne doit pas faire échouer le balayage.
    """
    try:
        import winreg
    except ImportError:
        return []

    hives = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}
    entries: list[tuple[str, str, str]] = []

    for hive_name, subkey in AUTOSTART_KEYS:
        try:
            with winreg.OpenKey(hives[hive_name], subkey) as key:
                index = 0
                while True:
                    try:
                        name, value, _kind = winreg.EnumValue(key, index)
                    except OSError:
                        break  # plus d'entrées
                    entries.append((f"{hive_name}\\{subkey}", name, str(value)))
                    index += 1
        except OSError:
            continue  # clé absente ou droits insuffisants

    return entries


def _read_startup_folder() -> list[tuple[str, str, str]]:
    """Raccourcis du dossier Démarrage, résolus via le registre."""
    try:
        import winreg
    except ImportError:
        return []

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            raw, _ = winreg.QueryValueEx(key, STARTUP_FOLDER_KEY)
        folder = Path(os.path.expandvars(raw))
    except OSError:
        return []

    if not folder.is_dir():
        return []

    return [
        ("Dossier Démarrage", item.name, str(item))
        for item in folder.iterdir()
        if item.is_file()
    ]


class PersistenceWatch:
    """
    Inventorie ce qui se lance au démarrage de Windows.

    `history` est injecté comme pour PrivacyShield : sans lui, le capteur
    fait l'inventaire mais ne sait pas dire ce qui est nouveau.
    """

    def __init__(
        self,
        log_event: Callable[[str, str], None] | None = None,
        history=None,
    ) -> None:
        self.log_event = log_event
        self.history = history

    @staticmethod
    def _is_volatile(command: str) -> bool:
        lowered = command.lower()
        return any(directory in lowered for directory in VOLATILE_DIRECTORIES)

    def scan(self) -> list[Finding]:
        entries = _read_registry_autostarts() + _read_startup_folder()
        findings: list[Finding] = []

        for source, name, command in entries:
            if self._is_volatile(command):
                findings.append(Finding(
                    severity=CRITICAL,
                    kind="autostart_volatile",
                    summary=(
                        f"« {name} » se lance au démarrage depuis un répertoire "
                        "temporaire. Aucun logiciel installé proprement ne fait ça."
                    ),
                    evidence={"entree": name, "commande": command[:120], "source": source},
                ))
                continue

            if self.history is not None and self.history.is_new(f"autostart|{name}|{command}"):
                findings.append(Finding(
                    severity=WARNING,
                    kind="autostart_new",
                    summary=(
                        f"Nouvelle entrée de démarrage automatique : « {name} ». "
                        "Elle n'était pas là au balayage précédent."
                    ),
                    evidence={"entree": name, "commande": command[:120], "source": source},
                ))

        if entries:
            findings.append(Finding(
                severity=INFO,
                kind="autostart_inventory",
                summary=f"{len(entries)} programme(s) se lancent au démarrage.",
                evidence={"total": len(entries)},
            ))

        if self.history is not None:
            self.history.save()

        self._log(findings)
        return findings

    def _log(self, findings: list[Finding]) -> None:
        if self.log_event is None:
            return
        for finding in findings:
            if finding.severity == INFO:
                continue
            event_type, details = finding.as_event()
            self.log_event(event_type, details)
