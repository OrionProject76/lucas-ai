# test_daemon_cleanup.py — le ménage nocturne atteint-il vraiment les fichiers ?
#
# Régression à empêcher, constatée en vrai le 13/08/2026 (ROADMAP.md §5.92) :
# `nightly_cleanup` cherchait les captures avec `glob("*.png")`, à la racine
# de `data/screenshots/` seulement, alors que `capture_screenshot` les
# écrivait dans des sous-dossiers datés. La règle « +7 jours » n'a donc
# jamais supprimé un seul fichier, pendant que le journal affichait « 0
# screenshots anciens supprimés » — un ménage qui se croyait fait. 5 461
# captures et 5,86 Go accumulés avant que quelqu'un compte.
#
# Le test met donc les fichiers là où ils allaient RÉELLEMENT : dans des
# sous-dossiers. Un test sur des fichiers à la racine serait passé au vert
# sur le code bogué.

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import pytest

import lucas_daemon
from lucas_daemon import LucasDaemon


def _dated_png(root: Path, day: str, name: str, age_days: float) -> Path:
    """Crée une capture dans son sous-dossier daté, vieillie de `age_days`."""
    path = root / day / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"png")
    old = time.time() - age_days * 86400
    os.utime(path, (old, old))
    return path


@pytest.fixture
def daemon(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LucasDaemon:
    """Un daemon dont tous les chemins pointent vers tmp_path.

    Sans ça, le test viderait les `__pycache__` du vrai dépôt et écrirait
    dans la vraie base du daemon.
    """
    shots = tmp_path / "screenshots"
    shots.mkdir()
    db = tmp_path / "lucas_daemon.db"
    sqlite3.connect(db).close()

    monkeypatch.setattr(lucas_daemon, "SCREENSHOTS_DIR", shots)
    monkeypatch.setattr(lucas_daemon, "LUCAS_ROOT", tmp_path)
    monkeypatch.setattr(lucas_daemon, "DB_FILE", db)
    monkeypatch.setattr(lucas_daemon, "LOG_FILE", tmp_path / "daemon.log")
    monkeypatch.setattr(lucas_daemon, "db_log_task", lambda *a, **k: None)
    return LucasDaemon()


def test_deletes_old_screenshots_inside_dated_subdirs(daemon: LucasDaemon) -> None:
    """Le cas exact du bug : les vieilles captures sont en sous-dossier."""
    shots = lucas_daemon.SCREENSHOTS_DIR
    old = _dated_png(shots, "2026-07-29", "11-11-50.png", age_days=15)

    daemon.nightly_cleanup()

    assert not old.exists()


def test_keeps_recent_screenshots_inside_dated_subdirs(daemon: LucasDaemon) -> None:
    """La règle reste « +7 jours » : le récent ne bouge pas."""
    shots = lucas_daemon.SCREENSHOTS_DIR
    recent = _dated_png(shots, "2026-08-13", "00-42-41.png", age_days=1)

    daemon.nightly_cleanup()

    assert recent.exists()
    assert recent.parent.exists(), "un dossier encore peuplé ne doit pas partir"


def test_removes_emptied_date_dirs_but_keeps_populated_ones(daemon: LucasDaemon) -> None:
    """Purger les fichiers ne doit pas laisser une coquille par jour."""
    shots = lucas_daemon.SCREENSHOTS_DIR
    _dated_png(shots, "2026-07-29", "11-11-50.png", age_days=15)
    _dated_png(shots, "2026-08-13", "00-42-41.png", age_days=1)

    daemon.nightly_cleanup()

    assert not (shots / "2026-07-29").exists()
    assert (shots / "2026-08-13").exists()
    assert shots.exists(), "le dossier racine se conserve, le daemon le rouvre"


def test_leaves_non_png_files_alone(daemon: LucasDaemon) -> None:
    """Le ménage vise les captures, pas tout ce qui traîne."""
    shots = lucas_daemon.SCREENSHOTS_DIR
    other = shots / "2026-07-29" / "notes.txt"
    other.parent.mkdir(parents=True)
    other.write_text("a garder")
    old = time.time() - 15 * 86400
    os.utime(other, (old, old))

    daemon.nightly_cleanup()

    assert other.exists()


def test_survives_an_empty_screenshots_dir(daemon: LucasDaemon) -> None:
    """État réel après la purge du 13/08 : plus rien à nettoyer."""
    daemon.nightly_cleanup()

    assert lucas_daemon.SCREENSHOTS_DIR.exists()


def test_cutoff_is_seven_days(daemon: LucasDaemon) -> None:
    """Garde-fou sur la frontière elle-même, pas seulement sur le balayage."""
    shots = lucas_daemon.SCREENSHOTS_DIR
    just_under = _dated_png(shots, "j-6", "a.png", age_days=6)
    just_over = _dated_png(shots, "j-8", "b.png", age_days=8)

    daemon.nightly_cleanup()

    assert just_under.exists()
    assert not just_over.exists()
