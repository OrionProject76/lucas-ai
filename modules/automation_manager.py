# modules/automation_manager.py — ouverture d'applications sur liste blanche
#
# C'est le module que citent VISION_LONG_TERME.md §4 et ROADMAP.md quand
# ils parlent de « liste blanche pour toute action système à risque ».
# Rien d'autre que ce qui figure dans WHITELISTED_APPS ne peut être lancé.
#
# Observation importante : la liste blanche ne vaut que par ce qu'elle
# contient. Une entrée qui donne accès à un interpréteur de commandes
# (cmd, powershell, wscript…) annule la protection entière, puisqu'on
# peut tout lancer depuis là. Voir la note sur `cmd` plus bas.

import subprocess
from collections.abc import Callable
from pathlib import Path

# Applications autorisées. Clés en minuscules : la comparaison normalise.
# Chaque valeur est une liste d'arguments passée telle quelle à Popen —
# jamais une chaîne, jamais shell=True, pour qu'aucune injection ne soit
# possible via le nom demandé.
WHITELISTED_APPS: dict[str, list[str]] = {
    "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe"],
    "calculatrice": [r"C:\Windows\System32\calc.exe"],
    "notepad": [r"C:\Windows\System32\notepad.exe"],
    "explorer": [r"C:\Windows\Explorer.exe"],
}

# ⚠️ `cmd` a été RETIRÉ de la liste blanche le 01/08/2026 (décision de
# Cyril, ROADMAP §5.1). Un interpréteur de commandes permet de lancer
# n'importe quel programme : le laisser dans une liste blanche revient à
# n'en avoir aucune.
#
# La détection ci-dessous reste en place pour plus tard : le jour où un
# shell sera réintroduit — derrière une confirmation explicite, quand le
# moteur de décision existera — son ouverture devra rester distinguable
# d'une ouverture ordinaire dans le journal.
SHELL_LIKE_APPS = frozenset({"cmd", "powershell", "pwsh", "wscript", "cscript", "bash"})


class AutomationManager:
    """
    Ouvre une application de la liste blanche.

    `log_event` est injecté, comme dans security/ et voice_manager : toute
    action système doit laisser une trace, sans que ce module connaisse
    LucasCore.
    """

    def __init__(
        self,
        log_event: Callable[[str, str], None] | None = None,
        whitelist: dict[str, list[str]] | None = None,
    ) -> None:
        self.whitelist = whitelist if whitelist is not None else dict(WHITELISTED_APPS)
        self.log_event = log_event

    def is_allowed(self, app_name: str) -> bool:
        return app_name.strip().lower() in self.whitelist

    def open_app(self, app_name: str) -> str:
        """
        Lance une application autorisée. Retourne toujours un message
        lisible, jamais d'exception : l'appelant est l'UI ou le LLM.
        """
        normalized = app_name.strip().lower()

        if normalized not in self.whitelist:
            self._log("automation_refused", app_name)
            return f"Application non autorisée : « {app_name} »"

        command = self.whitelist[normalized]

        # Vérifier l'existence avant de lancer permet un message utile
        # (« Chrome n'est pas installé à cet emplacement ») plutôt qu'un
        # FileNotFoundError générique.
        if not Path(command[0]).exists():
            self._log("automation_missing", normalized)
            return (
                f"L'application {normalized} est autorisée mais introuvable "
                f"à l'emplacement attendu : {command[0]}"
            )

        try:
            # Liste d'arguments figée, jamais construite depuis une entrée
            # utilisateur : le nom demandé sert de clé, pas de commande.
            subprocess.Popen(command)
        except OSError as e:
            self._log("automation_failed", f"{normalized} : {e}")
            return f"Erreur : {normalized} n'a pas pu être ouverte. {e}"

        self._log(
            "automation_shell_opened" if normalized in SHELL_LIKE_APPS
            else "automation_opened",
            normalized,
        )
        return f"L'application {normalized} a été ouverte."

    def list_allowed(self) -> list[str]:
        """Applications que Luca's peut ouvrir, triées."""
        return sorted(self.whitelist)

    def _log(self, event_type: str, details: str) -> None:
        if self.log_event is not None:
            self.log_event(event_type, details[:200])
