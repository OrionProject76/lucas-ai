# test_security_status.py — état affichable des capteurs niveau 1
# (panneau des privilèges, IDEAS.md #78)
#
# Deux vraies bases SQLite temporaires par test, jamais les fichiers réels
# du projet (data/lucas_daemon.db, memory/lucas_memory.db) — mêmes raisons
# que partout ailleurs dans cette suite : un test ne doit jamais dépendre
# de ce qui tourne sur le poste qui l'exécute, ni pouvoir l'altérer.

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest

from security.status import STALE_AFTER, get_status


def _daemon_db(path, rows=()):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE daemon_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            duration_seconds REAL,
            details TEXT,
            error TEXT
        )
    """)
    for task_name, status, started_at in rows:
        conn.execute(
            "INSERT INTO daemon_runs (task_name, status, started_at) VALUES (?, ?, ?)",
            (task_name, status, started_at),
        )
    conn.commit()
    conn.close()


def _memory_db(path, events=()):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE system_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for event_type, details, created_at in events:
        conn.execute(
            "INSERT INTO system_events (event_type, details, created_at) VALUES (?, ?, ?)",
            (event_type, details, created_at),
        )
    conn.commit()
    conn.close()


@pytest.fixture
def daemon_db(tmp_path):
    return tmp_path / "lucas_daemon.db"


@pytest.fixture
def memory_db(tmp_path):
    return tmp_path / "lucas_memory.db"


# ── Fraîcheur (active / daemon éteint) ─────────────────────────────────

def test_recent_successful_scan_is_active(daemon_db, memory_db) -> None:
    now = datetime.now().isoformat()
    _daemon_db(daemon_db, [("security_runtime", "success", now)])
    _memory_db(memory_db)

    status = get_status(daemon_db, memory_db)
    assert status.active is True
    assert status.last_scan_at == now


def test_a_failed_scan_still_counts_as_alive(daemon_db, memory_db) -> None:
    """
    Un balayage qui plante prouve que le daemon tourne — c'est le
    SILENCE total qui doit inquiéter, pas une erreur journalisée.
    """
    now = datetime.now().isoformat()
    _daemon_db(daemon_db, [("security_filesystem", "failed", now)])
    _memory_db(memory_db)

    assert get_status(daemon_db, memory_db).active is True


def test_a_started_but_unfinished_scan_does_not_count(daemon_db, memory_db) -> None:
    """
    « started » existe même si le processus a planté avant la fin — s'y
    fier ferait croire le daemon vivant sur la base d'un balayage mort.
    """
    now = datetime.now().isoformat()
    _daemon_db(daemon_db, [("security_runtime", "started", now)])
    _memory_db(memory_db)

    assert get_status(daemon_db, memory_db).active is False


def test_a_stale_scan_is_reported_inactive(daemon_db, memory_db) -> None:
    old = (datetime.now() - STALE_AFTER - timedelta(minutes=1)).isoformat()
    _daemon_db(daemon_db, [("security_runtime", "success", old)])
    _memory_db(memory_db)

    status = get_status(daemon_db, memory_db)
    assert status.active is False
    # ⚠️ last_scan_at reste renseigné même si stale : « il y a 40 minutes »
    # est une information utile, ce n'est pas la même chose que « jamais ».
    assert status.last_scan_at == old


def test_an_unrelated_task_does_not_count_as_a_security_scan(daemon_db, memory_db) -> None:
    now = datetime.now().isoformat()
    _daemon_db(daemon_db, [("morning_report", "success", now)])
    _memory_db(memory_db)

    assert get_status(daemon_db, memory_db).active is False


def test_no_daemon_db_at_all_is_reported_inactive_not_an_error(daemon_db, memory_db) -> None:
    """Avant le premier lancement du daemon, le fichier n'existe pas encore."""
    _memory_db(memory_db)
    status = get_status(daemon_db, memory_db)
    assert status.active is False
    assert status.last_scan_at is None


def test_a_corrupted_daemon_db_is_reported_inactive_not_a_crash(daemon_db, memory_db) -> None:
    """
    Différent du fichier absent : celui-ci existe mais n'est pas une base
    SQLite valide (table daemon_runs manquante, fichier tronqué...).
    """
    daemon_db.write_bytes(b"ceci n'est pas une base sqlite")
    _memory_db(memory_db)

    status = get_status(daemon_db, memory_db)
    assert status.active is False
    assert status.last_scan_at is None


def test_a_malformed_timestamp_is_treated_as_inactive(daemon_db, memory_db) -> None:
    """Un started_at illisible ne doit pas faire planter le panneau."""
    _daemon_db(daemon_db, [("security_runtime", "success", "pas-une-date")])
    _memory_db(memory_db)

    status = get_status(daemon_db, memory_db)
    assert status.active is False
    assert status.last_scan_at == "pas-une-date", "l'horodatage brut reste affiché même illisible"


# ── Signaux (findings) ──────────────────────────────────────────────────

def test_findings_within_24h_are_counted(daemon_db, memory_db) -> None:
    now = datetime.now().isoformat()
    _daemon_db(daemon_db)
    _memory_db(memory_db, [
        ("security_process_lookalike", "Process svch0st.exe imite svchost.exe | pid=1234", now),
        ("security_wide_open_listener", "Port 9999 ouvert à tout le réseau | port=9999", now),
    ])

    status = get_status(daemon_db, memory_db)
    assert status.findings_24h == 2


def test_findings_older_than_24h_are_excluded(daemon_db, memory_db) -> None:
    old = (datetime.now() - timedelta(hours=25)).isoformat()
    _daemon_db(daemon_db)
    _memory_db(memory_db, [("security_ransom_extension", "Extension suspecte | ext=.locked", old)])

    assert get_status(daemon_db, memory_db).findings_24h == 0


def test_non_security_events_are_not_counted_as_findings(daemon_db, memory_db) -> None:
    """
    system_events contient aussi app_launched, ram_alert... — seuls les
    signaux security_* relèvent du panneau des privilèges.
    """
    now = datetime.now().isoformat()
    _daemon_db(daemon_db)
    _memory_db(memory_db, [
        ("app_launched", "Chrome", now),
        ("ram_alert", "RAM à 91%", now),
    ])

    assert get_status(daemon_db, memory_db).findings_24h == 0


def test_the_latest_summary_is_the_most_recent_finding(daemon_db, memory_db) -> None:
    _daemon_db(daemon_db)
    _memory_db(memory_db, [
        ("security_process_lookalike", "Ancien signal | pid=1", "2026-08-01T10:00:00"),
        ("security_wide_open_listener", "Signal le plus récent | port=9999", "2026-08-02T20:00:00"),
    ])

    assert get_status(daemon_db, memory_db).latest_summary == "Signal le plus récent"


def test_the_summary_excludes_the_raw_evidence_facts(daemon_db, memory_db) -> None:
    """
    Finding.as_event() stocke « résumé | faits » (security/types.py) — le
    panneau affiche le résumé lisible, pas les paires clé=valeur brutes.
    """
    now = datetime.now().isoformat()
    _daemon_db(daemon_db)
    _memory_db(memory_db, [
        ("security_process_lookalike", "Résumé lisible | pid=1234, chemin=C:\\temp\\x.exe", now),
    ])

    assert get_status(daemon_db, memory_db).latest_summary == "Résumé lisible"


def test_no_memory_db_at_all_reports_zero_findings_not_an_error(daemon_db, memory_db) -> None:
    _daemon_db(daemon_db)
    status = get_status(daemon_db, memory_db)
    assert status.findings_24h == 0
    assert status.latest_summary is None


def test_a_corrupted_memory_db_reports_zero_findings_not_a_crash(daemon_db, memory_db) -> None:
    """Différent du fichier absent : celui-ci existe mais n'est pas une base SQLite valide."""
    _daemon_db(daemon_db)
    memory_db.write_bytes(b"ceci n'est pas une base sqlite")

    status = get_status(daemon_db, memory_db)
    assert status.findings_24h == 0
    assert status.latest_summary is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
