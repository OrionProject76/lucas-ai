# security/ransomware_watch.py — détection de chiffrement massif (observation seule)
#
# ⚠️ CHOIX DE CONCEPTION ACTUEL : ce capteur ne lit JAMAIS le contenu des
# fichiers de Cyril. Tout repose sur des métadonnées — noms, extensions,
# dates de modification — et sur des fichiers-appâts que Luca's a
# elle-même créés.
#
# L'approche habituelle serait de mesurer l'entropie du contenu pour
# repérer ce qui vient d'être chiffré — plus fiable, mais oblige le
# capteur à ouvrir les documents personnels. **Décision de Cyril,
# 03/08/2026 : ACCEPTÉE, mais scopée.** Pas un balayage permanent du
# disque (reviendrait à ouvrir tous les documents en continu) : un
# watcher événementiel, qui ne mesure l'entropie qu'en réaction à une
# rafale d'écritures/renommages détectée par les signaux déjà en place
# ci-dessous (extensions, notes de rançon) — l'entropie confirme un
# signal existant, elle ne surveille pas seule. Prêt à être développé
# quand ce chantier sera priorisé (voir ROADMAP.md §4, IDEAS.md #84) —
# pas construit à ce jour, ce fichier reste métadonnées-seules.
#
# Ne restaure rien, ne bloque rien, ne tue aucun process.

import time
from collections.abc import Callable
from pathlib import Path

from config import (
    RANSOMWARE_BURST_THRESHOLD,
    RANSOMWARE_BURST_WINDOW_MINUTES,
    RANSOMWARE_MAX_FILES_SCANNED,
    RANSOMWARE_WATCH_DIRS,
)
from security.types import CRITICAL, INFO, WARNING, Finding

# Extensions ajoutées par des rançongiciels connus après chiffrement.
# Un seul fichier suffit à alerter : aucun logiciel légitime ne renomme
# les documents de l'utilisateur avec ces suffixes.
RANSOM_EXTENSIONS = frozenset({
    ".locked", ".encrypted", ".crypt", ".crypto", ".enc", ".cry",
    ".wncry", ".wcry", ".wnry", ".locky", ".zepto", ".odin", ".thor",
    ".cerber", ".zzzzz", ".micro", ".ryk", ".conti", ".makop",
    ".djvu", ".stop", ".phobos", ".deadbolt", ".basslock", ".lockbit",
})

# Fragments de noms de « notes de rançon » déposées dans les répertoires.
RANSOM_NOTE_MARKERS = (
    "how_to_decrypt", "how-to-decrypt", "howtodecrypt",
    "decrypt_instruction", "decrypt-instruction",
    "recover_files", "recover-my-files", "restore_files",
    "your_files_are_encrypted", "readme_for_decrypt",
    "please_read_me", "!!!read_me", "_readme.txt",
)

# Contenu des fichiers-appâts. Volontairement inoffensif et explicite :
# si Cyril tombe dessus, il doit comprendre en une lecture.
CANARY_FILENAME = "_luca_s_ne_pas_modifier.txt"
CANARY_CONTENT = (
    "Fichier-appât créé par Luca's pour détecter un chiffrement malveillant.\n"
    "Ne pas modifier, ne pas supprimer, ne pas renommer.\n"
    "Si ce fichier change, Luca's le signale immédiatement.\n"
)


# Correspondance entre nos noms de config et les clés du registre Windows.
# Passer par le registre est indispensable : sur cette machine, Documents,
# Bureau et Images sont redirigés vers OneDrive. Deviner « ~/Documents »
# faisait surveiller un dossier vide — un capteur silencieux qui ne
# regarde rien est pire que pas de capteur du tout.
SHELL_FOLDER_KEYS = {
    "Documents": "Personal",
    "Desktop": "Desktop",
    "Pictures": "My Pictures",
}


def _resolve_shell_folder(name: str) -> Path | None:
    """Chemin réel d'un dossier connu Windows, redirection OneDrive comprise."""
    registry_name = SHELL_FOLDER_KEYS.get(name)
    if registry_name is None:
        return None
    try:
        import os
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            raw, _ = winreg.QueryValueEx(key, registry_name)
        return Path(os.path.expandvars(raw))
    except (ImportError, OSError):
        return None  # hors Windows, ou clé absente


def _watched_directories() -> list[Path]:
    """
    Répertoires surveillés. Le registre fait foi ; le nom sous le profil
    utilisateur ne sert que de repli si le registre est muet.
    """
    directories: list[Path] = []
    home = Path.home()

    for name in RANSOMWARE_WATCH_DIRS:
        resolved = _resolve_shell_folder(name)
        if resolved is None or not resolved.is_dir():
            resolved = home / name
        if resolved.is_dir() and resolved not in directories:
            directories.append(resolved)

    return directories


class RansomwareWatch:
    """
    Capteur de chiffrement massif. `scan()` retourne des signaux, jamais
    une action. `log_event` est injecté, comme les autres capteurs.
    """

    def __init__(self, log_event: Callable[[str, str], None] | None = None) -> None:
        self.log_event = log_event

    # ── Fichiers-appâts ───────────────────────────────────────────────

    def deploy_canaries(self) -> list[Path]:
        """
        Dépose un fichier-appât dans chaque répertoire surveillé.

        ⚠️ À appeler DÉLIBÉRÉMENT : c'est la seule opération de ce module
        qui écrit sur le disque de Cyril. Elle n'est jamais déclenchée
        automatiquement par scan(), pour qu'aucun fichier n'apparaisse
        dans ses dossiers sans qu'il l'ait voulu.

        Retourne la liste des appâts en place.
        """
        deployed = []
        for directory in _watched_directories():
            canary = directory / CANARY_FILENAME
            try:
                if not canary.exists():
                    canary.write_text(CANARY_CONTENT, encoding="utf-8")
                deployed.append(canary)
            except OSError:
                continue  # répertoire en lecture seule : on passe
        return deployed

    def _check_canaries(self) -> list[Finding]:
        """
        Un appât modifié ou disparu est le signal le plus fiable dont on
        dispose : aucun usage normal ne touche à ce fichier.
        """
        findings = []
        for directory in _watched_directories():
            canary = directory / CANARY_FILENAME
            if not canary.exists():
                continue  # jamais déployé ici, ou supprimé — voir plus bas

            try:
                content = canary.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                findings.append(Finding(
                    severity=CRITICAL,
                    kind="canary_unreadable",
                    summary=(
                        f"Le fichier-appât de {directory.name} est devenu illisible. "
                        "C'est le comportement attendu d'un chiffrement en cours."
                    ),
                    evidence={"fichier": str(canary)},
                ))
                continue

            if content != CANARY_CONTENT:
                findings.append(Finding(
                    severity=CRITICAL,
                    kind="canary_modified",
                    summary=(
                        f"Le fichier-appât de {directory.name} a été modifié. "
                        "Aucun usage normal ne touche à ce fichier."
                    ),
                    evidence={"fichier": str(canary)},
                ))
        return findings

    # ── Métadonnées ───────────────────────────────────────────────────

    def _scan_metadata(self) -> list[Finding]:
        """
        Parcourt les répertoires surveillés et relève trois signaux :
        extensions de rançongiciel, notes de rançon, rafale de
        modifications récentes.

        Le parcours est borné par RANSOMWARE_MAX_FILES_SCANNED : un scan
        qui met deux minutes ne serait jamais lancé.
        """
        now = time.time()
        window = RANSOMWARE_BURST_WINDOW_MINUTES * 60

        ransom_extensions: list[Path] = []
        ransom_notes: list[Path] = []
        recently_modified = 0
        examined = 0

        directories = _watched_directories()
        if not directories:
            return []

        # Budget réparti par répertoire, et non consommé globalement : sinon
        # un Bureau à 9000 fichiers épuiserait le quota et Images ne serait
        # jamais regardé. Chaque dossier surveillé doit l'être réellement.
        budget = max(1, RANSOMWARE_MAX_FILES_SCANNED // len(directories))

        for directory in directories:
            seen_here = 0
            for path in directory.rglob("*"):
                if seen_here >= budget:
                    break
                try:
                    if not path.is_file():
                        continue
                    examined += 1
                    seen_here += 1

                    if path.suffix.lower() in RANSOM_EXTENSIONS:
                        ransom_extensions.append(path)

                    lowered = path.name.lower()
                    if any(marker in lowered for marker in RANSOM_NOTE_MARKERS):
                        ransom_notes.append(path)

                    if now - path.stat().st_mtime <= window:
                        recently_modified += 1
                except OSError:
                    continue

        return self._build_findings(
            ransom_extensions, ransom_notes, recently_modified, examined
        )

    def _build_findings(
        self,
        extensions: list[Path],
        notes: list[Path],
        recently_modified: int,
        examined: int,
    ) -> list[Finding]:
        findings: list[Finding] = []

        if extensions:
            findings.append(Finding(
                severity=CRITICAL,
                kind="ransom_extension",
                summary=(
                    f"{len(extensions)} fichier(s) portent une extension de rançongiciel connu. "
                    "Aucun logiciel légitime ne renomme des documents ainsi."
                ),
                evidence={
                    "exemple": str(extensions[0]),
                    "extension": extensions[0].suffix,
                    "total": len(extensions),
                },
            ))

        if notes:
            findings.append(Finding(
                severity=CRITICAL,
                kind="ransom_note",
                summary=(
                    f"{len(notes)} fichier(s) ressemblent à une note de rançon "
                    "déposée dans tes dossiers."
                ),
                evidence={"exemple": str(notes[0]), "total": len(notes)},
            ))

        # La rafale seule ne prouve rien — une copie de sauvegarde ou un
        # export produisent le même motif. D'où WARNING et non CRITIQUE.
        if recently_modified >= RANSOMWARE_BURST_THRESHOLD:
            findings.append(Finding(
                severity=WARNING,
                kind="mass_modification",
                summary=(
                    f"{recently_modified} fichiers modifiés en moins de "
                    f"{RANSOMWARE_BURST_WINDOW_MINUTES} minutes. "
                    "Normal pour une sauvegarde ou une synchronisation, "
                    "anormal si tu n'as rien lancé."
                ),
                evidence={
                    "fichiers_modifies": recently_modified,
                    "fenetre_minutes": RANSOMWARE_BURST_WINDOW_MINUTES,
                },
            ))

        if examined >= RANSOMWARE_MAX_FILES_SCANNED:
            findings.append(Finding(
                severity=INFO,
                kind="scan_truncated",
                summary=(
                    f"Balayage interrompu à {examined} fichiers : la surveillance "
                    "n'a pas couvert l'intégralité des dossiers."
                ),
                evidence={"limite": RANSOMWARE_MAX_FILES_SCANNED},
            ))

        return findings

    # ── Balayage ──────────────────────────────────────────────────────

    def scan(self) -> list[Finding]:
        """Appâts d'abord — c'est le signal le plus fiable — puis métadonnées."""
        findings = self._check_canaries() + self._scan_metadata()
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
