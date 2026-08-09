# memory/memory_manager.py — sauvegarde et relit l'historique des conversations
# + événements système significatifs (voir VISION_LONG_TERME.md, mémoire 3 niveaux)

import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from config import MAX_HISTORY_MESSAGES

DB_PATH = Path(__file__).parent / "lucas_memory.db"

# Bump à chaque migration de schéma qui doit déclencher une sauvegarde
# automatique (_backup_if_migrating) — 1 = état avant la mémoire à 5
# types (Brique 3, 08/08/2026), 2 = état avant la colonne action_log.params
# (Brique 2, OS Controller, 08/08/2026), 3 = état avant la table cloud_usage
# (Brique 1, routeur hybride, 08/08/2026), 4 = état avant la table
# sandbox_runs (Workspace E-3, 09/08/2026).
SCHEMA_VERSION = 5

# Mémoire à 5 types (IDEAS.md #2) — distincte du transcript de chat
# (`conversations`) : un fait retenu, pas un message. Listes en Python,
# jamais un CHECK SQL — même style que router.py/automation_manager.py.
MEMORY_TYPES = frozenset({
    "episodic", "semantic", "procedural", "emotional", "prospective",
})
SOURCE_TYPES = frozenset({"conversation", "system_event", "os_controller", "manual"})


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

    ⚠️ `db_path=DB_PATH` explicite, jamais `MemoryManager()` bare. Trouvé
    le 08/08/2026 (Brique 3, ROADMAP.md §5.68) : `db_path: Path = DB_PATH`
    dans `__init__` est un défaut figé À LA DÉFINITION de la fonction
    (même piège que celui déjà documenté dans `MemoryManager.__init__`,
    ROADMAP.md §5.32) — un `monkeypatch.setattr(mm, "DB_PATH", ...)` dans
    un test ne change QUE le nom de module, jamais ce défaut déjà lié.
    `MemoryManager()` bare ignorait donc silencieusement toute isolation
    de test et écrivait sur la VRAIE base à chaque appel. Référencer
    `DB_PATH` ici, dans le corps de la fonction, relit la valeur du
    module À CHAQUE APPEL — c'est ce qui rend le monkeypatch efficace.
    """
    memory = None
    try:
        memory = MemoryManager(db_path=DB_PATH)
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
        # Conservé (05/08/2026) pour qu'un appelant puisse VÉRIFIER sur
        # quelle base il écrit, au lieu de le supposer. Ajouté après un
        # incident réel : une campagne de mesure croyait travailler sur une
        # copie isolée et écrivait en fait dans la base de Cyril — la valeur
        # par défaut d'un paramètre est figée à la définition de la
        # fonction, donc réassigner DB_PATH après l'import ne change rien.
        # Voir ROADMAP.md §5.32.
        self.db_path = db_path
        self._backup_if_migrating()
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._create_tables()
        self.set_state("schema_version", str(SCHEMA_VERSION))

    def _backup_if_migrating(self) -> None:
        """
        Copie physique de la base AVANT toute migration de schéma, si une
        base existante n'est pas encore à la version courante — jamais
        après. Idempotent : une base déjà à jour ne redéclenche rien au
        démarrage suivant. Sonde sa propre connexion temporaire, avant
        l'ouverture de self.conn, pour ne modifier aucun schéma tant que
        la copie de secours n'existe pas.
        """
        if not self.db_path.exists():
            return
        current_version = 1
        try:
            probe = sqlite3.connect(self.db_path)
            try:
                probe_cursor = probe.cursor()
                probe_cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='app_state'"
                )
                if probe_cursor.fetchone() is not None:
                    probe_cursor.execute(
                        "SELECT value FROM app_state WHERE key = 'schema_version'"
                    )
                    row = probe_cursor.fetchone()
                    if row is not None:
                        current_version = int(row[0])
            finally:
                probe.close()
        except (sqlite3.Error, ValueError):
            current_version = 1
        if current_version >= SCHEMA_VERSION:
            return
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        backup_path = self.db_path.with_name(f"{self.db_path.name}.bak-{timestamp}")
        shutil.copy2(self.db_path, backup_path)

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

        # Journal des actions gouvernées par core/decision_engine.py (ajout
        # 04/08/2026, premier câblage réel — voir ROADMAP.md §5.25). Table
        # DÉDIÉE et distincte de system_events : celle-ci trace une DÉCISION
        # de gouvernance (autorisée ou refusée, et par quoi déclenchée), pas
        # un événement système quelconque — automation_manager.py continue
        # par ailleurs de journaliser ses propres détails d'exécution
        # (appli manquante, erreur OS...) dans system_events, sans changement.
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                source TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # params : JSON sérialisé, nullable — ajouté pour core/os_controller.py
        # (Brique 2, 08/08/2026). Additif, rétrocompatible : tout appelant
        # existant de save_action() (lancement d'appli) continue de
        # fonctionner sans modification, params reste NULL pour lui.
        self._migrate_add_column("action_log", "params", "TEXT")

        # État persistant clé/valeur — voir set_state/get_state plus bas
        # pour la raison (LucasCore est recréé à chaque requête, donc tout
        # état en mémoire vive meurt entre deux messages).
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

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

        # Mémoire à 5 types (IDEAS.md #2, Brique 3 — 08/08/2026) : table
        # dédiée plutôt qu'une colonne memory_type sur conversations/
        # system_events — un souvenir n'est pas un message de chat, et
        # conversations a déjà 30+ appelants qui dépendent de sa forme
        # actuelle. source_type/source_id remplacent un texte de
        # provenance libre : la provenance doit rester vérifiable
        # (retrouver la ligne source), pas juste descriptive.
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                agent_id TEXT NOT NULL DEFAULT 'orion_main',
                source_type TEXT NOT NULL DEFAULT 'manual',
                source_id INTEGER,
                confidence REAL NOT NULL DEFAULT 1.0,
                importance REAL NOT NULL DEFAULT 0.5,
                date TIMESTAMP,
                last_validated TIMESTAMP,
                expiration TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_type_expiration
            ON memories(memory_type, expiration)
        """)

        # Compteur de coût cloud mensuel (Brique 1, routeur hybride,
        # 08/08/2026) — une ligne par mois, mise à jour incrémentale via
        # ON CONFLICT (même patron que set_state() plus bas). Sert
        # core/router.py::cloud_budget_available()/cloud_budget_warning().
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS cloud_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year_month TEXT NOT NULL UNIQUE,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cost_eur REAL NOT NULL DEFAULT 0.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Zone sandbox du Workspace (E-3, cowork_workspace/BRIEF_WORKSPACE_E3_SANDBOX.md,
        # 09/08/2026) : une proposition de code, son statut, et le résultat
        # de son exécution isolée s'il y en a eu une. Table dédiée plutôt
        # qu'une réutilisation d'action_log — une proposition sandbox a un
        # cycle de vie (pending → executed/rejected) qu'action_log ne
        # modélise pas (une ligne d'action_log est déjà terminée à
        # l'écriture, jamais mise à jour ensuite).
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sandbox_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                stdout TEXT,
                stderr TEXT,
                exit_code INTEGER,
                timed_out INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                decided_at TIMESTAMP
            )
        """)

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

    # ── Journal des actions gouvernées (Decision Engine, nouveau) ────

    def save_action(
        self, action: str, source: str, result: str, *, params: dict | None = None
    ) -> None:
        """
        Enregistre une décision de core/decision_engine.py — pas un
        événement système générique. `result` typiquement "executed" ou
        "denied" (voir core/decision_engine.py::ActionCategory), `source`
        le déclencheur de la demande (ex. "chat", "os_controller").

        `params` (ajouté 08/08/2026 pour core/os_controller.py) : les
        arguments de l'action, sérialisés en JSON — NULL si absent, tout
        appelant existant (lancement d'appli) continue sans modification.
        """
        self.cursor.execute(
            "INSERT INTO action_log (action, source, result, params) VALUES (?, ?, ?, ?)",
            (action, source, result, json.dumps(params) if params is not None else None),
        )
        self.conn.commit()

    def load_recent_actions(self, limit: int = 20) -> list[dict]:
        """
        Les N actions gouvernées les plus récentes — consultation future
        par le panneau sécurité/API (pas construit ici, voir ROADMAP.md
        §5.25 pour le périmètre exact de ce qui est câblé aujourd'hui).

        `params` est désérialisé depuis son JSON — `None` si absent, ou si
        une ligne pré-migration ne portait rien.
        """
        self.cursor.execute(
            """
            SELECT action, source, result, params, created_at
            FROM action_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        columns = ("action", "source", "result", "params", "created_at")
        rows = [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        for row in rows:
            row["params"] = json.loads(row["params"]) if row["params"] is not None else None
        return rows

    # ── Mémoire à 5 types (remember/recall/forget, IDEAS.md #2) ───────
    #
    # Distincte de save_message()/save_event() : ceux-ci tracent CE QUI
    # S'EST DIT ou CE QUI S'EST PASSÉ (transcript, journal), remember()
    # trace UN FAIT retenu, réutilisable par le chat et par
    # core/os_controller.py ("Cyril range ses factures dans D:\Factures").
    # Utilisée par le chat ET l'OS Controller à travers le même
    # MemoryManager — pas de mécanisme parallèle.

    def remember(
        self,
        memory_type: str,
        content: str,
        *,
        source_type: str = "manual",
        source_id: int | None = None,
        confidence: float = 1.0,
        importance: float = 0.5,
        expiration: str | None = None,
    ) -> int:
        """Enregistre un souvenir typé. Retourne son id. Lève ValueError sur un type inconnu."""
        if memory_type not in MEMORY_TYPES:
            raise ValueError(
                f"Type de mémoire inconnu : {memory_type!r} (attendu : {sorted(MEMORY_TYPES)})"
            )
        if source_type not in SOURCE_TYPES:
            raise ValueError(
                f"Type de provenance inconnu : {source_type!r} (attendu : {sorted(SOURCE_TYPES)})"
            )
        self.cursor.execute(
            """
            INSERT INTO memories
                (memory_type, content, source_type, source_id, confidence,
                 importance, date, last_validated, expiration)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
            """,
            (memory_type, content, source_type, source_id, confidence, importance, expiration),
        )
        self.conn.commit()
        assert self.cursor.lastrowid is not None  # garanti juste après un INSERT réussi
        return self.cursor.lastrowid

    def recall(
        self,
        memory_type: str | None = None,
        *,
        limit: int = 10,
        min_confidence: float = 0.0,
        include_expired: bool = False,
    ) -> list[dict]:
        """Relit des souvenirs, du plus récent au plus ancien. memory_type=None -> tous les types."""
        # Clauses fixes, jamais construites depuis une entrée utilisateur —
        # même raisonnement que _migrate_add_column ci-dessus.
        clauses = ["confidence >= ?"]
        params: list = [min_confidence]
        if memory_type is not None:
            clauses.append("memory_type = ?")
            params.append(memory_type)
        if not include_expired:
            clauses.append("(expiration IS NULL OR expiration > CURRENT_TIMESTAMP)")
        where = " AND ".join(clauses)
        params.append(limit)
        self.cursor.execute(
            f"""
            SELECT id, memory_type, content, source_type, source_id,
                   confidence, importance, date, last_validated, expiration, created_at
            FROM memories
            WHERE {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        )
        columns = (
            "id", "memory_type", "content", "source_type", "source_id",
            "confidence", "importance", "date", "last_validated", "expiration", "created_at",
        )
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    def forget(self, memory_id: int) -> bool:
        """Supprime définitivement un souvenir. True si une ligne existait."""
        self.cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0

    # ── Coût cloud mensuel (Brique 1, routeur hybride, 08/08/2026) ───────

    def record_cloud_usage(self, input_tokens: int, output_tokens: int, cost_eur: float) -> None:
        """
        Accumule l'usage cloud du mois courant. `year_month` calculé côté
        Python (UTC), jamais `strftime('%Y-%m', 'now')` en SQL — cohérent
        avec `created_at`/`CURRENT_TIMESTAMP` déjà en UTC ailleurs dans ce
        fichier (voir minutes_since_last_exchange()).
        """
        year_month = datetime.now(UTC).strftime("%Y-%m")
        self.cursor.execute(
            """
            INSERT INTO cloud_usage (year_month, input_tokens, output_tokens, cost_eur, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(year_month) DO UPDATE SET
                input_tokens = input_tokens + excluded.input_tokens,
                output_tokens = output_tokens + excluded.output_tokens,
                cost_eur = cost_eur + excluded.cost_eur,
                updated_at = CURRENT_TIMESTAMP
            """,
            (year_month, input_tokens, output_tokens, cost_eur),
        )
        self.conn.commit()

    def cloud_usage_this_month(self) -> dict:
        """
        Usage cloud du mois courant. `{"input_tokens": 0, "output_tokens": 0,
        "cost_eur": 0.0}` si rien n'a encore été enregistré ce mois-ci —
        jamais None, pour que core/router.py puisse comparer directement
        sans vérification supplémentaire.
        """
        year_month = datetime.now(UTC).strftime("%Y-%m")
        self.cursor.execute(
            "SELECT input_tokens, output_tokens, cost_eur FROM cloud_usage WHERE year_month = ?",
            (year_month,),
        )
        row = self.cursor.fetchone()
        if row is None:
            return {"input_tokens": 0, "output_tokens": 0, "cost_eur": 0.0}
        return {"input_tokens": row[0], "output_tokens": row[1], "cost_eur": row[2]}

    # ── État persistant léger (clé/valeur) ────────────────────────────
    #
    # ⚠️ Pourquoi une table plutôt qu'un attribut Python : `LucasCore` est
    # RECRÉÉ à chaque requête (api/server.py, contrainte SQLite/threads
    # documentée dans CLAUDE.md). Tout état gardé en mémoire vive meurt
    # donc entre deux messages. Le mode Deep Focus est « collant » par
    # conception — activé par une commande explicite, il reste actif
    # jusqu'à désactivation explicite : sans persistance, il s'éteignait
    # tout seul au message suivant, c'est-à-dire qu'il ne marchait pas.
    #
    # Volontairement générique et minuscule : une table clé/valeur, pas un
    # « système de préférences ». Le jour où il en faut un vrai, il se
    # construira sur autre chose que ceci.

    def set_state(self, key: str, value: str) -> None:
        """Écrit (ou remplace) une valeur d'état persistante."""
        self.cursor.execute(
            "INSERT INTO app_state (key, value, updated_at) "
            "VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = CURRENT_TIMESTAMP",
            (key, value),
        )
        self.conn.commit()

    def get_state(self, key: str, default: str | None = None) -> str | None:
        """Relit une valeur d'état persistante, `default` si absente."""
        self.cursor.execute("SELECT value FROM app_state WHERE key = ?", (key,))
        row = self.cursor.fetchone()
        return row[0] if row else default

    def minutes_since_last_exchange(self) -> float | None:
        """
        Minutes écoulées depuis l'avant-dernier message enregistré.

        ⚠️ AVANT-dernier, pas dernier : au moment où ceci est appelé, la
        question courante VIENT d'être enregistrée par `ask()`. Mesurer
        depuis le dernier message rendrait donc toujours ~0 — un signal de
        présence qui ne dit rien.

        None quand il n'y a pas d'échange antérieur (première question de
        la base) : l'appelant doit pouvoir distinguer « je ne sais pas » de
        « à l'instant », deux situations opposées pour choisir un ton.
        """
        self.cursor.execute(
            "SELECT created_at FROM conversations ORDER BY id DESC LIMIT 1 OFFSET 1"
        )
        row = self.cursor.fetchone()
        if row is None or not row[0]:
            return None
        try:
            # DTZ007 assumé : `%z` serait FAUX ici. `created_at` vient de
            # CURRENT_TIMESTAMP, qui n'écrit aucun fuseau — la valeur est
            # UTC par convention, pas par notation. La comparaison en UTC
            # naïf, quatre lignes plus bas, est ce qui rend l'ensemble
            # correct.
            precedent = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
        except (TypeError, ValueError):
            return None
        # created_at est écrit par CURRENT_TIMESTAMP, donc en UTC : la
        # comparaison se fait en UTC aussi, sinon l'écart vaudrait le
        # décalage horaire (2 h en été) même sur un message à l'instant.
        #
        # `datetime.now(UTC)` et non `utcnow()` : ce dernier est déprécié
        # depuis Python 3.12 et programmé pour disparaître. Le `.replace(
        # tzinfo=None)` ramène à un datetime naïf, parce que `precedent`
        # l'est aussi — soustraire un aware d'un naïf lève.
        maintenant = datetime.now(UTC).replace(tzinfo=None)
        return (maintenant - precedent).total_seconds() / 60

    # ── Zone sandbox du Workspace (E-3, nouveau, 09/08/2026) ──────────
    #
    # save_sandbox_run() ne fait qu'enregistrer une PROPOSITION, jamais
    # l'exécuter — modules/sandbox_manager.py décide seul quand (et si)
    # une exécution isolée a lieu. Cette table ne contient donc aucune
    # logique d'exécution, seulement l'état.

    _SANDBOX_RUN_COLUMNS = (
        "id", "code", "status", "stdout", "stderr",
        "exit_code", "timed_out", "created_at", "decided_at",
    )

    def save_sandbox_run(self, code: str) -> int:
        """Enregistre une proposition de code, statut 'pending'. Retourne son id."""
        self.cursor.execute(
            "INSERT INTO sandbox_runs (code, status) VALUES (?, 'pending')",
            (code,),
        )
        self.conn.commit()
        assert self.cursor.lastrowid is not None  # garanti juste après un INSERT réussi
        return self.cursor.lastrowid

    def get_sandbox_run(self, run_id: int) -> dict | None:
        """Une proposition sandbox par id, ou None si l'id est inconnu."""
        self.cursor.execute(
            f"SELECT {', '.join(self._SANDBOX_RUN_COLUMNS)} FROM sandbox_runs WHERE id = ?",
            (run_id,),
        )
        row = self.cursor.fetchone()
        if row is None:
            return None
        result = dict(zip(self._SANDBOX_RUN_COLUMNS, row))
        result["timed_out"] = bool(result["timed_out"])
        return result

    def update_sandbox_run(
        self,
        run_id: int,
        *,
        status: str,
        stdout: str | None = None,
        stderr: str | None = None,
        exit_code: int | None = None,
        timed_out: bool | None = None,
    ) -> None:
        """
        Fait passer une proposition 'pending' à un statut décidé
        (executed/rejected), avec le résultat d'exécution s'il y en a un.
        `decided_at` horodate ce passage — jamais réécrit ensuite, une
        proposition n'est tranchée qu'une fois (voir
        modules/sandbox_manager.py, qui refuse un second execute()/reject()
        sur une proposition déjà décidée).
        """
        self.cursor.execute(
            """
            UPDATE sandbox_runs
            SET status = ?, stdout = ?, stderr = ?, exit_code = ?,
                timed_out = ?, decided_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, stdout, stderr, exit_code, int(bool(timed_out)), run_id),
        )
        self.conn.commit()

    def load_recent_sandbox_runs(self, limit: int = 20) -> list[dict]:
        """Les N propositions sandbox les plus récentes, les plus récentes en premier."""
        self.cursor.execute(
            f"""
            SELECT {', '.join(self._SANDBOX_RUN_COLUMNS)}
            FROM sandbox_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = []
        for row in self.cursor.fetchall():
            entry = dict(zip(self._SANDBOX_RUN_COLUMNS, row))
            entry["timed_out"] = bool(entry["timed_out"])
            rows.append(entry)
        return rows

    def close(self):
        self.conn.close()
