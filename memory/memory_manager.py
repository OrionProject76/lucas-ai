# memory/memory_manager.py — sauvegarde et relit l'historique des conversations
# + événements système significatifs (voir VISION_LONG_TERME.md, mémoire 3 niveaux)

import sqlite3
from pathlib import Path

from config import MAX_HISTORY_MESSAGES

DB_PATH = Path(__file__).parent / "lucas_memory.db"


def save_event_from_any_thread(event_type: str, details: str = "") -> bool:
    """
    Enregistre un événement depuis n'importe quel thread.

    SQLite refuse d'être utilisé depuis un autre thread que celui qui a
    ouvert la connexion. Partager une instance de MemoryManager entre le
    thread principal et un worker lève « SQLite objects created in a
    thread can only be used in that same thread » — c'est ce qui se
    produisait quand l'UI passait son LucasCore.log_event au TTSWorker.

    Cette fonction ouvre sa propre connexion, écrit, referme. Le coût est
    négligeable et tout l'état vit dans le fichier, pas en mémoire Python
    — même raisonnement que dans api/server.py.

    Retourne False plutôt que de propager : un événement perdu dégrade la
    trace, une exception dans un thread de fond fait tomber l'appelant.
    """
    memory = None
    try:
        memory = MemoryManager()
        memory.save_event(event_type, details)
        return True
    except Exception:  # noqa: BLE001 — voir docstring
        return False
    finally:
        if memory is not None:
            try:
                memory.close()
            except Exception as e:  # noqa: BLE001 — une connexion non
                # refermée fuit une ressource : à voir, pas à taire.
                print(f"[Mémoire] Fermeture de connexion impossible : {e}")


class MemoryManager:
    def __init__(self, db_path: Path = DB_PATH):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Nouvelle table — événements système significatifs uniquement.
        # Pas un log de chaque tick : juste les faits qui comptent
        # (lancement d'appli, alerte RAM, changement de mode...).
        # Voir ROADMAP.md / VISION_LONG_TERME.md : "pas de persistance
        # lourde, pas de GraphRAG" — cette table reste volontairement simple.
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    # ── Conversations (inchangé) ──────────────────────────────

    def save_message(self, role: str, message: str):
        self.cursor.execute(
            "INSERT INTO conversations (role, message) VALUES (?, ?)",
            (role, message),
        )
        self.conn.commit()
        self._cleanup_old_messages()

    def _cleanup_old_messages(self):
        """Garde seulement les N derniers messages pour éviter une base infinie."""
        self.cursor.execute("""
            DELETE FROM conversations
            WHERE id NOT IN (
                SELECT id FROM conversations
                ORDER BY id DESC
                LIMIT ?
            )
        """, (MAX_HISTORY_MESSAGES,))
        self.conn.commit()

    def load_history(self) -> list[tuple[str, str]]:
        self.cursor.execute(
            "SELECT role, message FROM conversations ORDER BY id"
        )
        return self.cursor.fetchall()

    def clear(self):
        self.cursor.execute("DELETE FROM conversations")
        self.conn.commit()

    def forget_last_exchange(self) -> int:
        """
        Efface le dernier échange (la question et la réponse qui suit).
        Retourne le nombre de messages supprimés.

        ⚠️ Ceci n'est pas un confort, c'est le complément indispensable au
        budget d'historique de config.py. Mesuré sur la base réelle de
        Cyril, question identique, 9 tirages : 3/9 avec l'historique tel
        quel, 8/9 en supprimant QUATRE messages — la même question déjà
        posée deux fois, et ses deux réponses génériques.

        Aucun réglage de prompt ne renverse ça : face à la question
        identique déjà répondue juste au-dessus, le modèle imite sa propre
        réponse, et c'est le comportement normal d'un modèle de langue.
        Le budget empêche une mauvaise réponse d'en contaminer cent ; il
        ne peut pas effacer celle qui vient d'être donnée. Il faut pouvoir
        la retirer.
        """
        self.cursor.execute("""
            DELETE FROM conversations
            WHERE id IN (SELECT id FROM conversations ORDER BY id DESC LIMIT 2)
        """)
        self.conn.commit()
        return self.cursor.rowcount

    # ── Événements système (nouveau) ──────────────────────────

    def save_event(self, event_type: str, details: str = ""):
        """
        Enregistre un événement système significatif.
        À appeler manuellement pour l'instant (pas de détection
        automatique en tâche de fond — ça viendra avec la proactivité,
        Phase 3 de ROADMAP.md).
        Exemples de event_type : "app_launched", "ram_alert", "mode_change".
        """
        self.cursor.execute(
            "INSERT INTO system_events (event_type, details) VALUES (?, ?)",
            (event_type, details),
        )
        self.conn.commit()

    def load_recent_events(self, limit: int = 5) -> list[tuple[str, str, str]]:
        """
        Retourne les N événements système les plus récents.
        Utilisé pour enrichir le contexte envoyé au LLM sans le noyer
        sous un historique complet.
        """
        self.cursor.execute("""
            SELECT event_type, details, created_at
            FROM system_events
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        return self.cursor.fetchall()

    def close(self):
        self.conn.close()
