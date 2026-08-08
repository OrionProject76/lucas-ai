# test_memory_manager.py — memory/memory_manager.py n'avait aucun fichier
# de test dédié (trouvé via mesure de couverture réelle, Priorité 3
# qualité/fiabilité, 04/08/2026). MemoryManager est construit dans de
# nombreux autres fichiers (test_history_budget.py, test_voice_router.py,
# test_ui_workers.py, test_integration.py), mais jamais pour exercer
# clear(), load_recent_events() ou la migration de schéma elles-mêmes —
# ailleurs c'est toujours une fausse mémoire qui réimplémente ces
# méthodes. load_recent_events() n'est exercée en réel que dans
# test_integration.py (marqueur "integration", exclu du run par défaut).
#
# SQLite réel à chaque fois (fichier tmp_path) : c'est un test unitaire
# rapide, pas un mock — aucune bibliothèque externe à isoler ici.

from __future__ import annotations

import sqlite3

import pytest

from memory.memory_manager import MemoryManager


@pytest.fixture
def memory(tmp_path):
    instance = MemoryManager(db_path=tmp_path / "test.db")
    yield instance
    instance.close()


# ── clear() : jamais appelé par aucun test ──────────────────────────────

def test_clear_removes_all_conversation_messages(memory) -> None:
    memory.save_message("user", "a")
    memory.save_message("assistant", "b")

    memory.clear()

    assert memory.load_history() == []


# ── load_recent_events() : jamais exercé en dehors du run "integration" ─

def test_load_recent_events_returns_most_recent_first(memory) -> None:
    memory.save_event("app_launched", "Chrome")
    memory.save_event("ram_alert", "RAM à 91%")

    events = memory.load_recent_events(limit=5)

    assert [event_type for event_type, _, _ in events] == ["ram_alert", "app_launched"]
    assert events[0][1] == "RAM à 91%"


def test_load_recent_events_respects_the_limit(memory) -> None:
    for i in range(5):
        memory.save_event(f"event_{i}")

    assert len(memory.load_recent_events(limit=2)) == 2


# ── Migration de schéma : agent_id ajouté après coup ────────────────────

def test_migrates_an_old_database_without_the_agent_id_column(tmp_path) -> None:
    """
    Les deux tables existaient déjà, chez Cyril, avant l'ajout de la
    colonne agent_id : CREATE TABLE IF NOT EXISTS ne touche pas un schéma
    déjà présent, la migration ALTER TABLE doit s'exécuter — et aucun test
    ne créait jamais une base avec l'ancien schéma pour la déclencher.
    """
    db_path = tmp_path / "old_schema.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE system_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "INSERT INTO conversations (role, message) VALUES (?, ?)",
        ("user", "question d'avant la migration"),
    )
    conn.commit()
    conn.close()

    memory = MemoryManager(db_path=db_path)
    try:
        columns = {
            row[1] for row in memory.cursor.execute("PRAGMA table_info(conversations)").fetchall()
        }
        assert "agent_id" in columns
        assert memory.load_history() == [("user", "question d'avant la migration")]
    finally:
        memory.close()


def test_migration_is_a_no_op_on_an_already_migrated_database(tmp_path) -> None:
    """Rouvrir une base déjà migrée ne doit pas lever (colonne déjà présente)."""
    db_path = tmp_path / "already_migrated.db"
    MemoryManager(db_path=db_path).close()

    memory = MemoryManager(db_path=db_path)
    try:
        memory.save_message("user", "après une seconde ouverture")
        assert memory.load_history() == [("user", "après une seconde ouverture")]
    finally:
        memory.close()


# ── Confiance & provenance (IDEAS.md #2bis, 04/08/2026) ─────────────────
#
# Chaque souvenir porte désormais d'où il vient et à quel point on peut
# encore s'y fier — objectif de fond : repondérer plus tard Reasoning
# Engine et RAG sur la fiabilité réelle d'un souvenir, pas juste son
# existence. Rien n'est câblé sur cette exploitation ici : ce chantier ne
# construit que le socle (schéma + lecture/écriture), délibérément.

def test_new_tables_carry_the_confidence_and_provenance_columns(memory) -> None:
    for table in ("conversations", "system_events"):
        columns = {
            row[1] for row in memory.cursor.execute(f"PRAGMA table_info({table})").fetchall()
        }
        assert {"source", "date", "confidence", "last_validated", "importance", "expiration"} <= columns


def test_a_message_gets_sensible_defaults_without_the_caller_changing_anything(memory) -> None:
    """Aucun appelant existant ne passe ces paramètres : les défauts doivent être utilisables tels quels."""
    memory.save_message("user", "bonjour")

    enrichi = memory.load_history_with_metadata()[0]
    assert enrichi["source"] == "conversation"
    assert enrichi["confidence"] == 1.0
    assert enrichi["importance"] == 0.5
    assert enrichi["date"] is not None
    assert enrichi["last_validated"] is not None
    assert enrichi["expiration"] is None


def test_an_event_gets_sensible_defaults(memory) -> None:
    memory.save_event("app_launched", "Chrome")

    enrichi = memory.load_recent_events_with_metadata()[0]
    assert enrichi["source"] == "system"
    assert enrichi["confidence"] == 1.0
    assert enrichi["importance"] == 0.5


def test_a_caller_can_override_confidence_and_provenance(memory) -> None:
    memory.save_message(
        "assistant",
        "il est probablement au bureau",
        source="screen_capture",
        confidence=0.4,
        importance=0.8,
        date="2026-08-01T10:00:00",
        last_validated="2026-08-03T09:00:00",
        expiration="2026-09-01T00:00:00",
    )

    enrichi = memory.load_history_with_metadata()[0]
    assert enrichi["source"] == "screen_capture"
    assert enrichi["confidence"] == 0.4
    assert enrichi["importance"] == 0.8
    assert enrichi["date"] == "2026-08-01T10:00:00"
    assert enrichi["last_validated"] == "2026-08-03T09:00:00"
    assert enrichi["expiration"] == "2026-09-01T00:00:00"


def test_load_history_keeps_its_existing_shape(memory) -> None:
    """
    Garde anti-régression : LucasCore._build_messages() et toute la suite
    de tests dépendent de la forme (role, message). L'enrichissement ne
    doit rien y changer.
    """
    memory.save_message("user", "bonjour", confidence=0.2, source="autre chose")
    assert memory.load_history() == [("user", "bonjour")]


def test_migrating_an_old_database_backfills_date_and_last_validated_from_created_at(tmp_path) -> None:
    """
    Un message déjà en base était vrai au moment où il a été observé —
    meilleure valeur par défaut disponible sans reconstituer un historique
    perdu, plutôt que laisser `date`/`last_validated` à NULL.
    """
    db_path = tmp_path / "old_schema_confidence.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE TABLE system_events (id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, details TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    conn.execute(
        "INSERT INTO conversations (role, message, created_at) VALUES (?, ?, ?)",
        ("user", "avant confiance/provenance", "2026-07-01T08:00:00"),
    )
    conn.commit()
    conn.close()

    memory = MemoryManager(db_path=db_path)
    try:
        enrichi = memory.load_history_with_metadata()[0]
        assert enrichi["date"] == "2026-07-01T08:00:00"
        assert enrichi["last_validated"] == "2026-07-01T08:00:00"
        assert enrichi["source"] == "conversation"
        assert enrichi["confidence"] == 1.0
        assert enrichi["importance"] == 0.5
    finally:
        memory.close()


# ── save_event_from_any_thread() : l'échec à la fermeture ───────────────

def test_thread_safe_logger_reports_a_close_failure_but_still_returns_true(
    monkeypatch, tmp_path, capsys
) -> None:
    """
    L'événement est bien écrit ; seule la fermeture de connexion échoue.
    Une connexion non refermée fuit une ressource — à signaler, pas à
    taire silencieusement, et surtout pas à faire échouer l'appelant pour
    autant : voir la docstring de save_event_from_any_thread().
    """
    from memory import memory_manager as mm

    monkeypatch.setattr(mm, "DB_PATH", tmp_path / "close_fail.db")
    monkeypatch.setattr(
        mm.MemoryManager, "close",
        lambda self: (_ for _ in ()).throw(RuntimeError("verrou SQLite")),
    )

    result = mm.save_event_from_any_thread("test", "détail")

    assert result is True
    assert "Fermeture de connexion impossible" in capsys.readouterr().out


# ── action_log (Decision Engine, premier câblage réel, 04/08/2026) ─────
#
# Table DÉDIÉE, distincte de system_events — voir core/lucas_core.py et
# ROADMAP.md §5.25 pour le câblage complet (chat -> Decision Engine ->
# automation_manager).

def test_save_action_then_load_recent_actions(memory) -> None:
    memory.save_action("launch_chrome", "chat", "executed")

    actions = memory.load_recent_actions()

    assert len(actions) == 1
    assert actions[0]["action"] == "launch_chrome"
    assert actions[0]["source"] == "chat"
    assert actions[0]["result"] == "executed"
    assert actions[0]["created_at"] is not None


def test_load_recent_actions_returns_most_recent_first(memory) -> None:
    memory.save_action("launch_notepad", "chat", "executed")
    memory.save_action("launch_photoshop", "chat", "denied")

    actions = memory.load_recent_actions()

    assert [a["action"] for a in actions] == ["launch_photoshop", "launch_notepad"]


def test_load_recent_actions_respects_the_limit(memory) -> None:
    for i in range(5):
        memory.save_action(f"launch_app{i}", "chat", "executed")

    assert len(memory.load_recent_actions(limit=2)) == 2


def test_load_recent_actions_is_empty_on_a_fresh_database(memory) -> None:
    assert memory.load_recent_actions() == []


# ── Mémoire à 5 types (remember/recall/forget, IDEAS.md #2, Brique 3) ───
#
# Distincte de save_message()/save_event() : ceux-ci tracent le transcript
# de chat / le journal système, remember() trace un FAIT retenu,
# réutilisable par le chat ET core/os_controller.py.

def test_remember_recall_round_trip_persists_metadata(tmp_path) -> None:
    """
    Couvre le critère V6 du brief : fermer/rouvrir sur le même fichier ne
    doit rien perdre, ni le contenu ni les métadonnées de confiance/
    provenance.
    """
    db_path = tmp_path / "memories.db"
    first = MemoryManager(db_path=db_path)
    try:
        memory_id = first.remember(
            "semantic",
            "Cyril range ses factures dans D:\\Factures",
            source_type="manual",
            confidence=0.9,
            importance=0.7,
        )
    finally:
        first.close()

    second = MemoryManager(db_path=db_path)
    try:
        souvenirs = second.recall("semantic")
        assert len(souvenirs) == 1
        souvenir = souvenirs[0]
        assert souvenir["id"] == memory_id
        assert souvenir["content"] == "Cyril range ses factures dans D:\\Factures"
        assert souvenir["source_type"] == "manual"
        assert souvenir["confidence"] == 0.9
        assert souvenir["importance"] == 0.7
        assert souvenir["date"] is not None
        assert souvenir["last_validated"] is not None
    finally:
        second.close()


def test_forget_removes_the_memory(memory) -> None:
    memory_id = memory.remember("procedural", "toujours confirmer avant de fermer Chrome")

    removed = memory.forget(memory_id)

    assert removed is True
    assert memory.recall("procedural") == []


def test_forget_returns_false_for_an_unknown_id(memory) -> None:
    assert memory.forget(9999) is False


def test_recall_filters_by_memory_type(memory) -> None:
    memory.remember("episodic", "a")
    memory.remember("semantic", "b")

    assert [m["content"] for m in memory.recall("semantic")] == ["b"]
    assert len(memory.recall()) == 2  # memory_type=None -> tous les types


def test_recall_respects_min_confidence(memory) -> None:
    memory.remember("semantic", "peu fiable", confidence=0.2)
    memory.remember("semantic", "fiable", confidence=0.9)

    souvenirs = memory.recall("semantic", min_confidence=0.5)

    assert [m["content"] for m in souvenirs] == ["fiable"]


def test_recall_excludes_expired_by_default(memory) -> None:
    memory.remember("prospective", "expiré", expiration="2020-01-01T00:00:00")
    memory.remember("prospective", "toujours valide", expiration="2099-01-01T00:00:00")

    assert [m["content"] for m in memory.recall("prospective")] == ["toujours valide"]
    assert len(memory.recall("prospective", include_expired=True)) == 2


def test_recall_returns_most_recent_first_and_respects_limit(memory) -> None:
    for i in range(3):
        memory.remember("semantic", f"fait {i}")

    souvenirs = memory.recall("semantic", limit=2)

    assert [m["content"] for m in souvenirs] == ["fait 2", "fait 1"]


def test_invalid_memory_type_is_rejected(memory) -> None:
    with pytest.raises(ValueError):
        memory.remember("inconnu", "contenu")


def test_invalid_source_type_is_rejected(memory) -> None:
    with pytest.raises(ValueError):
        memory.remember("episodic", "contenu", source_type="inconnu")


def test_source_id_is_nullable_for_manual_entries(memory) -> None:
    memory.remember("emotional", "contenu", source_type="manual")

    assert memory.recall("emotional")[0]["source_id"] is None


def test_source_id_can_reference_a_conversation(memory) -> None:
    """
    La provenance doit rester vérifiable (retrouver la ligne source), pas
    une chaîne descriptive libre — précision explicite de Cyril avant ce
    plan.
    """
    memory.remember(
        "episodic", "Cyril a demandé d'ouvrir Chrome",
        source_type="conversation", source_id=42,
    )

    assert memory.recall("episodic")[0]["source_id"] == 42


# ── Sauvegarde avant migration de schéma (SCHEMA_VERSION) ───────────────

def test_migration_backs_up_existing_db_and_is_additive(tmp_path) -> None:
    """
    Une base créée avant la mémoire à 5 types n'a pas de `memories` ni de
    `schema_version` à jour dans app_state — l'ouverture doit sauvegarder
    le fichier avant de migrer, et laisser conversations/system_events
    intactes.
    """
    db_path = tmp_path / "pre_memories.db"
    old = MemoryManager(db_path=db_path)
    old.save_message("user", "avant la brique memoire")
    # Redescend artificiellement à la version 1 : simule une base créée
    # avant l'introduction de schema_version elle-même.
    old.cursor.execute("DELETE FROM app_state WHERE key = 'schema_version'")
    old.cursor.execute("DROP TABLE memories")
    old.conn.commit()
    old.close()

    reopened = MemoryManager(db_path=db_path)
    try:
        backups = list(tmp_path.glob("pre_memories.db.bak-*"))
        assert len(backups) == 1
        assert reopened.load_history() == [("user", "avant la brique memoire")]
        tables = {
            row[0]
            for row in reopened.cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "memories" in tables
    finally:
        reopened.close()


def test_migration_backup_is_a_no_op_on_an_already_migrated_database(tmp_path) -> None:
    db_path = tmp_path / "already_at_v2.db"
    MemoryManager(db_path=db_path).close()

    MemoryManager(db_path=db_path).close()

    assert list(tmp_path.glob("already_at_v2.db.bak-*")) == []


# ── Coût cloud mensuel (Brique 1, routeur hybride, 08/08/2026) ──────────

def test_cloud_usage_this_month_is_zero_on_a_fresh_database(memory) -> None:
    assert memory.cloud_usage_this_month() == {
        "input_tokens": 0, "output_tokens": 0, "cost_eur": 0.0,
    }


def test_record_cloud_usage_accumulates_within_the_month(memory) -> None:
    memory.record_cloud_usage(input_tokens=1000, output_tokens=500, cost_eur=0.02)
    memory.record_cloud_usage(input_tokens=2000, output_tokens=1000, cost_eur=0.04)

    usage = memory.cloud_usage_this_month()

    assert usage["input_tokens"] == 3000
    assert usage["output_tokens"] == 1500
    assert usage["cost_eur"] == pytest.approx(0.06)


def test_cloud_usage_switches_to_local_only_at_100_percent(monkeypatch, tmp_path) -> None:
    """
    Reproduit le scénario de validation V3 du brief : plafond artificiel à
    0,01€, un seul appel suffit à le dépasser.
    """
    import config

    monkeypatch.setattr(config, "CLOUD_BUDGET_EUR", 0.01)
    memory = MemoryManager(db_path=tmp_path / "test.db")
    try:
        memory.record_cloud_usage(input_tokens=1000, output_tokens=500, cost_eur=0.02)
        assert memory.cloud_usage_this_month()["cost_eur"] >= config.CLOUD_BUDGET_EUR
    finally:
        memory.close()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
