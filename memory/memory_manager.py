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
        # agent_id : hook multi-agents (IDEAS.md #38, toujours reporté v1.1+
        # — CLAUDE.md règle 12) posé le 03/08/2026 à la demande de Cyril.
        # Valeur par défaut 'orion_main' identique pour tout le monde tant
        # qu'un seul agent existe — aucune requête ne filtre dessus
        # aujourd'hui, la colonne ne coûte rien et évite une migration plus
        # tard. 'orion_main' et pas 'lucas_main' : identifiant de stockage
        # interne, même logique que la collection ChromaDB `orion_docs`
        # restée inchangée (voir CLAUDE.md, "Renommage du projet").
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                agent_id TEXT NOT NULL DEFAULT 'orion_main',
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
                agent_id TEXT NOT NULL DEFAULT 'orion_main',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migration : les tables existaient déjà avant l'ajout de agent_id
        # (base réelle de Cyril comprise) — CREATE TABLE IF NOT EXISTS ne
        # touche pas un schéma déjà présent, un ALTER TABLE explicite est
        # nécessaire. Noms de tables/colonnes fixes, jamais une entrée
        # utilisateur — pas de risque d'injection dans ces f-strings.
        self._migrate_add_column("conversations", "agent_id", "TEXT NOT NULL DEFAULT 'orion_main'")
        self._migrate_add_column("system_events", "agent_id", "TEXT NOT NULL DEFAULT 'orion_main'")

        # Confiance & provenance (IDEAS.md #2bis, ajout 03/08/2026) : chaque
        # souvenir stocké porte désormais d'où il vient et à quel point on
        # peut encore s'y fier, pas seulement son contenu brut. Objectif de
        # fond (pas câblé ici, délibérément — voir la docstring du module) :
        # permettre plus tard de repondérer Reasoning Engine et RAG sur la
        # fiabilité réelle d'un souvenir. `date` et `last_validated` sont
        # rétro-remplis depuis `created_at` : un message déjà en base était
        # vrai au moment où il a été observé, ce qui est la meilleure valeur
        # par défaut disponible sans reconstituer un historique perdu.
        for table, default_source in (("conversations", "conversation"), ("system_events", "system")):
            self._migrate_add_column(table, "source", f"TEXT NOT NULL DEFAULT '{default_source}'")
            self._migrate_add_column(table, "date", "TIMESTAMP")
            self._migrate_add_column(table, "confidence", "REAL NOT NULL DEFAULT 1.0")
            self._migrate_add_column(table, "last_validated", "TIMESTAMP")
            self._migrate_add_column(table, "importance", "REAL NOT NULL DEFAULT 0.5")
            self._migrate_add_column(table, "expiration", "TIMESTAMP")
            # Idempotent (WHERE ... IS NULL) : sans coût sur une base déjà
            # rétro-remplie, donc sans danger à relancer à chaque démarrage.
            self.cursor.execute(f"UPDATE {table} SET date = created_at WHERE date IS NULL")
            self.cursor.execute(
                f"UPDATE {table} SET last_validated = created_at WHERE last_validated IS NULL"
            )

        self.conn.commit()

    def _migrate_add_column(self, table: str, column: str, ddl: str) -> None:
        """Ajoute une colonne si absente. Migration additive, jamais destructive."""
        self.cursor.execute(f"PRAGMA table_info({table})")
        columns = {row[1] for row in self.cursor.fetchall()}
        if column not in columns:
            self.cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    # ── Conversations (inchangé) ──────────────────────────────

    def save_message(
        self,
        role: str,
        message: str,
        *,
        source: str = "conversation",
        confidence: float = 1.0,
        importance: float = 0.5,
        date: str | None = None,
        last_validated: str | None = None,
        expiration: str | None = None,
    ):
        """
        Enregistre un message. Les paramètres confiance/provenance
        (IDEAS.md #2bis) ont tous une valeur par défaut : aucun appelant
        existant n'a besoin de changer pour continuer à fonctionner à
        l'identique.
        """
        self.cursor.execute(
            """
            INSERT INTO conversations
                (role, message, source, confidence, importance, date, last_validated, expiration)
            VALUES (?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), COALESCE(?, CURRENT_TIMESTAMP), ?)
            """,
            (role, message, source, confidence, importance, date, last_validated, expiration),
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

    def load_history_with_metadata(self) -> list[dict]:
        """
        Historique complet, confiance/provenance incluses.

        Forme séparée de load_history() plutôt qu'un changement de son
        format existant : LucasCore._build_messages() et toute la suite de
        tests en dépendent sous la forme (role, message) — l'exploitation
        réelle de ces métadonnées (repondération Reasoning Engine/RAG) est
        un chantier futur, pas celui-ci.
        """
        self.cursor.execute("""
            SELECT role, message, source, confidence, importance,
                   date, last_validated, expiration
            FROM conversations ORDER BY id
        """)
        columns = (
            "role", "message", "source", "confidence", "importance",
            "date", "last_validated", "expiration",
        )
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

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

    def save_event(
        self,
        event_type: str,
        details: str = "",
        *,
        source: str = "system",
        confidence: float = 1.0,
        importance: float = 0.5,
        date: str | None = None,
        last_validated: str | None = None,
        expiration: str | None = None,
    ):
        """
        Enregistre un événement système significatif.
        À appeler manuellement pour l'instant (pas de détection
        automatique en tâche de fond — ça viendra avec la proactivité,
        Phase 3 de ROADMAP.md).
        Exemples de event_type : "app_launched", "ram_alert", "mode_change".

        Paramètres confiance/provenance (IDEAS.md #2bis) : voir la
        docstring de save_message() pour le raisonnement, identique ici.
        """
        self.cursor.execute(
            """
            INSERT INTO system_events
                (event_type, details, source, confidence, importance, date, last_validated, expiration)
            VALUES (?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), COALESCE(?, CURRENT_TIMESTAMP), ?)
            """,
            (event_type, details, source, confidence, importance, date, last_validated, expiration),
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

    def load_recent_events_with_metadata(self, limit: int = 5) -> list[dict]:
        """Comme load_recent_events(), confiance/provenance incluses (voir load_history_with_metadata())."""
        self.cursor.execute("""
            SELECT event_type, details, source, confidence, importance,
                   date, last_validated, expiration
            FROM system_events
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        columns = (
            "event_type", "details", "source", "confidence", "importance",
            "date", "last_validated", "expiration",
        )
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    def close(self):
        self.conn.close()
