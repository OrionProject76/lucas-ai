# security/monitor.py — surveillance continue, orchestrée par le daemon
#
# Les trois capteurs (Guardian, Privacy Shield, Ransomware Watch) sont
# conçus pour un balayage à la demande. Ce module les fait tourner en
# boucle sans transformer la table d'événements en dépotoir.
#
# Le problème central d'une surveillance continue n'est pas de détecter,
# c'est de NE PAS répéter : un signal légitime mais permanent (« steam
# écoute sur toutes les interfaces ») serait enregistré toutes les cinq
# minutes, chasserait tout le reste du contexte de Luca's, et Cyril
# cesserait de lire les rapports. D'où la déduplication persistante.
#
# Toujours en observation seule : ce module n'agit pas davantage que les
# capteurs qu'il orchestre.

import json
import time
from collections.abc import Callable
from pathlib import Path

from security.guardian import Guardian
from security.privacy_shield import PrivacyShield
from security.ransomware_watch import RansomwareWatch
from security.types import INFO, Finding

DEFAULT_STATE_PATH = Path("data/security_state.json")

# Au-delà de ce délai sans être revu, un signal est oublié. S'il
# réapparaît ensuite, il est de nouveau signalé — un programme suspect
# qui revient après trois jours est une information, pas un doublon.
FORGET_AFTER_SECONDS = 3 * 24 * 3600


class SecurityMonitor:
    """
    Orchestre les capteurs et ne rapporte que ce qui est nouveau.

    `log_event` est injecté, comme partout ailleurs dans security/ :
    ce module ne connaît ni OrionCore ni MemoryManager.
    """

    def __init__(
        self,
        log_event: Callable[[str, str], None] | None = None,
        state_path: Path | str | None = None,
    ) -> None:
        self.log_event = log_event
        self.state_path = Path(state_path or DEFAULT_STATE_PATH)
        # Les capteurs ne journalisent pas eux-mêmes : c'est le moniteur
        # qui décide, après déduplication.
        self.guardian = Guardian()
        self.privacy_shield = PrivacyShield()
        self.ransomware_watch = RansomwareWatch()
        self._seen: dict[str, float] = self._load_state()

    # ── État persistant ───────────────────────────────────────────────

    def _load_state(self) -> dict[str, float]:
        """
        Empreintes déjà vues, relues du disque. La persistance compte :
        sans elle, chaque redémarrage du daemon rejouerait toutes les
        alertes en attente.
        """
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        now = time.time()
        return {
            fingerprint: seen_at
            for fingerprint, seen_at in raw.items()
            if isinstance(seen_at, (int, float)) and now - seen_at < FORGET_AFTER_SECONDS
        }

    def _save_state(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(self._seen, indent=2), encoding="utf-8")
        except OSError:
            pass  # un état non sauvegardé fait re-signaler, jamais planter

    # ── Balayages ─────────────────────────────────────────────────────

    def scan_runtime(self) -> list[Finding]:
        """Process et réseau — rapide, adapté à un passage fréquent."""
        return self._report_new(self.guardian.scan() + self.privacy_shield.scan())

    def scan_filesystem(self) -> list[Finding]:
        """Fichiers — plus lent, à espacer davantage."""
        return self._report_new(self.ransomware_watch.scan())

    def scan_all(self) -> list[Finding]:
        return self._report_new(
            self.guardian.scan() + self.privacy_shield.scan() + self.ransomware_watch.scan()
        )

    # ── Déduplication ─────────────────────────────────────────────────

    def _report_new(self, findings: list[Finding]) -> list[Finding]:
        """
        Retourne les seuls signaux jamais vus (ou oubliés depuis), et les
        journalise. Les signaux déjà connus voient leur horodatage
        rafraîchi pour ne pas être oubliés tant qu'ils persistent.
        """
        now = time.time()
        fresh: list[Finding] = []

        for finding in findings:
            fingerprint = finding.fingerprint()
            already_known = fingerprint in self._seen
            self._seen[fingerprint] = now
            if already_known:
                continue
            fresh.append(finding)
            if finding.severity != INFO and self.log_event is not None:
                event_type, details = finding.as_event()
                self.log_event(event_type, details)

        self._save_state()
        return fresh

    def forget_all(self) -> None:
        """Remet le compteur à zéro : tout sera de nouveau signalé."""
        self._seen = {}
        self._save_state()
