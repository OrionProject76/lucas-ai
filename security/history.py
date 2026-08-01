# security/history.py — mémoire des comportements observés
#
# Le niveau 0 des capteurs n'avait aucune mémoire : chaque balayage
# repartait de zéro. « Ce programme n'avait jamais parlé à Internet
# jusqu'à aujourd'hui » était donc indétectable — alors que c'est le
# signal le plus utile qui soit, un binaire légitime qui se met soudain
# à sortir étant exactement ce qu'on veut voir.
#
# Ce module ne juge rien : il retient ce qui a déjà été observé et répond
# à la question « est-ce nouveau ? ». Les capteurs décident.
#
# Rien n'est envoyé nulle part : le fichier reste sur la machine, à côté
# de l'état du moniteur (VISION_LONG_TERME.md §4.1).

import json
import time
from pathlib import Path

from config import SECURITY_HISTORY_RETENTION_DAYS, SECURITY_LEARNING_HOURS

# Chemins ancrés sur la racine du projet et non sur le répertoire
# courant. Le daemon est prévu pour tourner en service Windows via NSSM,
# depuis un CWD quelconque : un chemin relatif faisait atterrir l'état
# ailleurs à chaque lancement. Conséquence, la période d'apprentissage
# repartait de zéro et la déduplication aussi — la mémoire du niveau 1
# devenait inopérante précisément dans son déploiement cible.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HISTORY_PATH = PROJECT_ROOT / "data" / "security_history.json"


class BehaviourHistory:
    """
    Ce que la machine a l'habitude de faire.

    Chaque observation est une clé libre (« process|adresse »,
    « autostart|nom ») associée à ses dates de première et dernière vue.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path or DEFAULT_HISTORY_PATH)
        self._entries: dict[str, dict] = {}
        self._started_at = time.time()
        self._load()

    # ── Persistance ───────────────────────────────────────────────────

    def _load(self) -> None:
        """
        Relit l'historique. Un fichier illisible repart à vide plutôt que
        de faire échouer le capteur : perdre la mémoire dégrade la
        détection, planter la supprime entièrement.
        """
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(raw, dict):
            return

        entries = raw.get("entries")
        if isinstance(entries, dict):
            self._entries = {
                key: value
                for key, value in entries.items()
                if isinstance(value, dict) and "first_seen" in value
            }

        started = raw.get("started_at")
        if isinstance(started, (int, float)):
            self._started_at = started

        self._purge()

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(
                    {"started_at": self._started_at, "entries": self._entries},
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass  # un historique non sauvegardé re-signale, jamais ne plante

    def _purge(self) -> None:
        """Oublie ce qui n'a pas été revu depuis longtemps."""
        limit = time.time() - SECURITY_HISTORY_RETENTION_DAYS * 86400
        self._entries = {
            key: value
            for key, value in self._entries.items()
            if value.get("last_seen", 0) >= limit
        }

    # ── Période d'apprentissage ───────────────────────────────────────

    @property
    def is_learning(self) -> bool:
        """
        Vrai pendant les premières heures d'existence de l'historique.

        Sans cette période, le tout premier balayage signalerait chaque
        programme installé sur la machine comme « nouveau comportement ».
        Le rapport serait illisible et Cyril cesserait de le lire — c'est
        déjà ce qui a failli arriver au niveau 0 avec les services
        Windows.
        """
        return (time.time() - self._started_at) < SECURITY_LEARNING_HOURS * 3600

    def learning_remaining_hours(self) -> float:
        elapsed = time.time() - self._started_at
        return max(0.0, SECURITY_LEARNING_HOURS - elapsed / 3600)

    # ── Observation ───────────────────────────────────────────────────

    def has_seen(self, key: str) -> bool:
        return key in self._entries

    def remember(self, key: str) -> None:
        now = time.time()
        entry = self._entries.get(key)
        if entry is None:
            self._entries[key] = {"first_seen": now, "last_seen": now}
        else:
            entry["last_seen"] = now

    def is_new(self, key: str) -> bool:
        """
        Répond puis enregistre.

        L'ordre compte : enregistrer d'abord ferait répondre « déjà vu »
        à tout, et le capteur serait silencieux pour toujours.

        Pendant l'apprentissage, retourne toujours False — on observe
        sans alerter.
        """
        already_known = self.has_seen(key)
        self.remember(key)
        if self.is_learning:
            return False
        return not already_known

    def __len__(self) -> int:
        return len(self._entries)
