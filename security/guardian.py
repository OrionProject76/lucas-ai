# security/guardian.py — détection de process suspects (observation seule)
#
# Heuristiques locales uniquement. Aucune base de signatures, aucun appel
# réseau : envoyer la liste des process de Cyril à un service tiers serait
# la fuite même qu'on cherche à empêcher.
#
# Ne tue jamais un process. Voir security/__init__.py pour le niveau de
# maturité et ce que ça implique (VISION_LONG_TERME.md §4.1).

from collections.abc import Callable
from pathlib import PureWindowsPath

import psutil

from security.types import CRITICAL, INFO, WARNING, Finding

# Process système Windows dont le nom est massivement usurpé par les malwares.
# La technique classique : garder le nom exact, changer le répertoire.
# Un « svchost.exe » hors de System32 est un signal fort et peu bruyant.
SYSTEM_PROCESS_HOMES: dict[str, tuple[str, ...]] = {
    "svchost.exe": (r"c:\windows\system32", r"c:\windows\syswow64"),
    "lsass.exe": (r"c:\windows\system32",),
    "csrss.exe": (r"c:\windows\system32",),
    "winlogon.exe": (r"c:\windows\system32",),
    "services.exe": (r"c:\windows\system32",),
    "smss.exe": (r"c:\windows\system32",),
    "explorer.exe": (r"c:\windows",),
    "taskhostw.exe": (r"c:\windows\system32",),
}

# Répertoires d'où un exécutable n'a normalement rien à faire tourner
# durablement. Un binaire lancé depuis Temp est le mode de livraison
# classique d'une charge téléchargée.
VOLATILE_DIRECTORIES = (
    r"\appdata\local\temp",
    r"\windows\temp",
    r"\downloads",
    r"\$recycle.bin",
    r"\temporary internet files",
)

# Noms proches d'un process système, à une lettre ou un chiffre près.
# Le typosquatting vise l'œil humain qui parcourt le gestionnaire de tâches.
#
# ⚠️ Clés en minuscules obligatoirement : la comparaison passe par .lower(),
# donc « expIorer.exe » (I majuscule imitant un l minuscule) doit être
# enregistré ici sous « expiorer.exe ». Une clé avec une majuscule ne
# matcherait jamais — et c'est précisément ce sosie-là qu'on veut attraper.
LOOKALIKE_NAMES = {
    "svch0st.exe": "svchost.exe",
    "svchosts.exe": "svchost.exe",
    "scvhost.exe": "svchost.exe",
    "lsas.exe": "lsass.exe",
    "explor3r.exe": "explorer.exe",
    "expiorer.exe": "explorer.exe",  # I majuscule ou l minuscule : même clé
    "chr0me.exe": "chrome.exe",
    "rundll32.exe.exe": "rundll32.exe",
}


class Guardian:
    """
    Capteur de process. `scan()` retourne des signaux, jamais une action.

    `log_event` est injecté (même motif que VoiceManager) : security/ ne
    doit pas importer OrionCore, ça créerait un cycle.
    """

    def __init__(self, log_event: Callable[[str, str], None] | None = None) -> None:
        self.log_event = log_event

    # ── Heuristiques unitaires ────────────────────────────────────────

    @staticmethod
    def _check_system_impersonation(name: str, exe: str) -> Finding | None:
        """Nom de process système, mais lancé d'ailleurs que son répertoire."""
        expected = SYSTEM_PROCESS_HOMES.get(name.lower())
        if not expected or not exe:
            return None

        parent = str(PureWindowsPath(exe).parent).lower()
        if any(parent.startswith(home) for home in expected):
            return None

        return Finding(
            severity=CRITICAL,
            kind="process_impersonation",
            summary=(
                f"« {name} » tourne hors de son répertoire système habituel. "
                "C'est la signature classique d'un process qui usurpe un nom Windows."
            ),
            evidence={"process": name, "chemin": exe, "attendu": expected[0]},
        )

    @staticmethod
    def _check_lookalike_name(name: str, exe: str) -> Finding | None:
        """Nom volontairement proche d'un process légitime."""
        legitimate = LOOKALIKE_NAMES.get(name.lower())
        if not legitimate:
            return None
        return Finding(
            severity=CRITICAL,
            kind="process_lookalike",
            summary=(
                f"« {name} » imite « {legitimate} » à un caractère près. "
                "Ce type de nom ne vient jamais d'un éditeur légitime."
            ),
            evidence={"process": name, "imite": legitimate, "chemin": exe or "inconnu"},
        )

    @staticmethod
    def _check_volatile_location(name: str, exe: str) -> Finding | None:
        """Exécutable lancé depuis un répertoire temporaire."""
        if not exe:
            return None
        lowered = exe.lower()
        for directory in VOLATILE_DIRECTORIES:
            if directory in lowered:
                return Finding(
                    severity=WARNING,
                    kind="process_volatile_path",
                    summary=(
                        f"« {name} » s'exécute depuis un répertoire temporaire. "
                        "Légitime pour un installeur, inhabituel pour un process durable."
                    ),
                    evidence={"process": name, "chemin": exe, "repertoire": directory},
                )
        return None

    # ── Balayage ──────────────────────────────────────────────────────

    def scan(self) -> list[Finding]:
        """
        Parcourt les process visibles et retourne les signaux relevés.

        Les process inaccessibles (droits insuffisants) sont ignorés sans
        bruit : sous Windows, un utilisateur non-administrateur ne voit pas
        les process système, et en faire des alertes noierait les vrais
        signaux sous des dizaines de faux.
        """
        findings: list[Finding] = []

        for proc in psutil.process_iter(["name", "exe", "pid"]):
            try:
                info = proc.info
                name = info.get("name") or ""
                exe = info.get("exe") or ""
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

            if not name:
                continue

            for check in (
                self._check_system_impersonation,
                self._check_lookalike_name,
                self._check_volatile_location,
            ):
                finding = check(name, exe)
                if finding is not None:
                    finding.evidence["pid"] = info.get("pid", "?")
                    findings.append(finding)

        self._log(findings)
        return findings

    def _log(self, findings: list[Finding]) -> None:
        """
        Trace les signaux non triviaux. Les événements security_* restent
        locaux : la table system_events ne part jamais vers le cloud
        (voir OrionCore._build_messages).
        """
        if self.log_event is None:
            return
        for finding in findings:
            if finding.severity == INFO:
                continue
            event_type, details = finding.as_event()
            self.log_event(event_type, details)
