# test_memory_double.py — le minimum qu'un double de MemoryManager doit
# savoir faire pour que LucasCore fonctionne.
#
# ⚠️ Pourquoi ce fichier existe (05/08/2026)
# ------------------------------------------
# Cinq fichiers de test définissaient chacun leur propre `_FakeMemory` /
# `_Memoire`, recopié à la main. Ajouter UNE méthode à MemoryManager
# (get_state/set_state, pour le mode AURA persistant) a donc cassé
# 52 tests d'un coup, dans cinq fichiers, pour la même raison répétée
# cinq fois.
#
# Ce n'est pas seulement pénible : c'est précisément le motif « tests
# verts mais comportement jamais réel ». Cinq doubles écrits séparément
# dérivent séparément de l'objet réel, et chacun peut rester vert en
# simulant une interface qui n'existe plus.
#
# `MemoryDouble` réunit le socle commun. Les doubles existants n'ont pas
# été supprimés — chacun a ses particularités (historique injecté,
# actions journalisées) — mais ils en HÉRITENT désormais, ce qui veut dire
# qu'une méthode ajoutée ici les couvre tous d'un coup.

from __future__ import annotations


class MemoryDouble:
    """
    Socle commun des doubles de MemoryManager utilisés dans les tests.

    Ne touche jamais SQLite. Les sous-classes surchargent ce dont elles
    ont besoin (typiquement `load_history`).
    """

    def __init__(self) -> None:
        self.saved: list[tuple[str, str]] = []
        self.events: list[tuple[str, str]] = []
        self.actions_logged: list[dict] = []
        self.state: dict[str, str] = {}

    # ── Historique ────────────────────────────────────────────────────

    def save_message(self, role: str, content: str) -> None:
        self.saved.append((role, content))

    def load_history(self) -> list[tuple[str, str]]:
        return list(self.saved)

    def load_history_with_metadata(self) -> list[dict]:
        return [
            {
                "role": role,
                "message": message,
                "confidence": 1.0,
                "importance": 0.5,
                "expiration": None,
            }
            for role, message in self.load_history()
        ]

    # ── Événements système ────────────────────────────────────────────

    def save_event(self, event_type: str, details: str = "") -> None:
        self.events.append((event_type, details))

    def load_recent_events(self, limit: int = 5) -> list[tuple[str, str, str]]:
        return []

    def load_recent_events_with_metadata(self, limit: int = 5) -> list[dict]:
        return []

    # ── Journal d'actions gouvernées ──────────────────────────────────

    def save_action(self, action: str, source: str, result: str) -> None:
        self.actions_logged.append(
            {"action": action, "source": source, "result": result}
        )

    # ── État persistant (mode AURA « collant ») ───────────────────────

    def get_state(self, key: str, default: str | None = None) -> str | None:
        return self.state.get(key, default)

    def set_state(self, key: str, value: str) -> None:
        self.state[key] = value

    # ── Signal de présence ────────────────────────────────────────────

    def minutes_since_last_exchange(self) -> float | None:
        """None = « pas d'échange antérieur », le défaut le plus neutre."""
        return None

    def close(self) -> None:
        pass
