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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
