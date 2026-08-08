# test_workspace_manager.py — Workspace Luca's (IDEAS.md #102, E-1)
#
# Toutes les fonctions sont isolées de la vraie arborescence
# cowork_workspace/ et de la vraie base memory/lucas_memory.db :
# REPORTS_DIR/REQUESTS_DIR pointent vers tmp_path, DB_PATH vers un
# fichier tmp_path — même discipline que test_router.py
# (test_cloud_budget_available_reflects_real_usage).

from __future__ import annotations

import os
import time

from memory import memory_manager
from modules import workspace_manager


def test_list_reports_returns_empty_list_when_directory_is_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(workspace_manager, "REPORTS_DIR", tmp_path / "reports")
    assert workspace_manager.list_reports() == []


def test_list_pending_requests_returns_empty_list_when_directory_is_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(workspace_manager, "REQUESTS_DIR", tmp_path / "requests")
    assert workspace_manager.list_pending_requests() == []


def test_list_reports_sorts_newest_first_and_extracts_markdown_title(monkeypatch, tmp_path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    monkeypatch.setattr(workspace_manager, "REPORTS_DIR", reports_dir)

    older = reports_dir / "older.md"
    older.write_text("# Rapport plus ancien\n\nContenu.", encoding="utf-8")
    newer = reports_dir / "newer.md"
    newer.write_text("# Rapport plus récent\n\nContenu.", encoding="utf-8")

    # mtime explicite : deux écritures rapprochées peuvent partager la même
    # seconde sur certains systèmes de fichiers, rendant le tri par défaut
    # instable côté test.
    older_time = time.time() - 100
    newer_time = time.time()
    os.utime(older, (older_time, older_time))
    os.utime(newer, (newer_time, newer_time))

    reports = workspace_manager.list_reports()
    assert [r["filename"] for r in reports] == ["newer.md", "older.md"]
    assert reports[0]["title"] == "Rapport plus récent"
    assert reports[1]["title"] == "Rapport plus ancien"


def test_list_reports_falls_back_to_filename_for_non_markdown(monkeypatch, tmp_path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    monkeypatch.setattr(workspace_manager, "REPORTS_DIR", reports_dir)

    (reports_dir / "Audit.xlsx").write_bytes(b"binaire, pas du texte")

    reports = workspace_manager.list_reports()
    assert reports[0]["title"] == "Audit"
    assert reports[0]["filename"] == "Audit.xlsx"


def test_list_reports_falls_back_to_filename_when_no_markdown_heading(monkeypatch, tmp_path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    monkeypatch.setattr(workspace_manager, "REPORTS_DIR", reports_dir)

    (reports_dir / "sans_titre.md").write_text("Pas de titre ici.", encoding="utf-8")

    reports = workspace_manager.list_reports()
    assert reports[0]["title"] == "sans_titre"


def test_list_pending_requests_excludes_readme_and_done_files(monkeypatch, tmp_path) -> None:
    requests_dir = tmp_path / "requests"
    requests_dir.mkdir()
    monkeypatch.setattr(workspace_manager, "REQUESTS_DIR", requests_dir)

    (requests_dir / "README.md").write_text("# Guide", encoding="utf-8")
    (requests_dir / "request_2026-08-08_deja_traitee_DONE.md").write_text(
        "# Demande traitée", encoding="utf-8"
    )
    (requests_dir / "request_2026-08-08_en_attente.md").write_text(
        "# Demande en attente", encoding="utf-8"
    )

    pending = workspace_manager.list_pending_requests()
    assert [p["filename"] for p in pending] == ["request_2026-08-08_en_attente.md"]


def test_list_recent_actions_reads_the_real_action_log(monkeypatch, tmp_path) -> None:
    """
    ⚠️ db_path=memory_manager.DB_PATH explicite dans workspace_manager,
    jamais MemoryManager() nu : monkeypatch de DB_PATH ci-dessous ne
    change QUE la variable de module, un défaut de paramètre déjà figé à
    l'import ne le verrait jamais (même piège que core/router.py).
    """
    monkeypatch.setattr(memory_manager, "DB_PATH", tmp_path / "test_actions.db")

    memory = memory_manager.MemoryManager(db_path=tmp_path / "test_actions.db")
    try:
        memory.save_action("open_app:notepad", "chat", "executed", params={"app": "notepad"})
        memory.save_action("move_file", "os_controller", "denied")
    finally:
        memory.close()

    actions = workspace_manager.list_recent_actions()
    assert len(actions) == 2
    assert actions[0]["action"] == "move_file"  # le plus récent en premier
    assert actions[0]["result"] == "denied"
    assert actions[1]["params"] == {"app": "notepad"}


def test_list_recent_actions_returns_empty_list_when_nothing_logged(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(memory_manager, "DB_PATH", tmp_path / "test_no_actions.db")
    assert workspace_manager.list_recent_actions() == []


def test_list_objectives_reads_prospective_memories_only(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(memory_manager, "DB_PATH", tmp_path / "test_objectives.db")

    memory = memory_manager.MemoryManager(db_path=tmp_path / "test_objectives.db")
    try:
        memory.remember("prospective", "PEA à alimenter avant fin d'année", importance=0.8)
        memory.remember("semantic", "Un fait retenu, pas un objectif")  # ne doit pas apparaître
    finally:
        memory.close()

    objectives = workspace_manager.list_objectives()
    assert len(objectives) == 1
    assert objectives[0]["content"] == "PEA à alimenter avant fin d'année"
    assert objectives[0]["memory_type"] == "prospective"


def test_list_objectives_returns_empty_list_when_nothing_remembered(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(memory_manager, "DB_PATH", tmp_path / "test_no_objectives.db")
    assert workspace_manager.list_objectives() == []


def test_summary_assembles_all_four_sections(monkeypatch, tmp_path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    requests_dir = tmp_path / "requests"
    requests_dir.mkdir()
    monkeypatch.setattr(workspace_manager, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(workspace_manager, "REQUESTS_DIR", requests_dir)
    monkeypatch.setattr(memory_manager, "DB_PATH", tmp_path / "test_summary.db")

    (reports_dir / "Rapport.md").write_text("# Un rapport", encoding="utf-8")
    (requests_dir / "request_test.md").write_text("# Une demande", encoding="utf-8")

    memory = memory_manager.MemoryManager(db_path=tmp_path / "test_summary.db")
    try:
        memory.save_action("open_app:calc", "chat", "executed")
        memory.remember("prospective", "Objectif retraite 500k€")
    finally:
        memory.close()

    result = workspace_manager.summary()
    assert set(result.keys()) == {"reports", "pending_requests", "recent_actions", "objectives"}
    assert len(result["reports"]) == 1
    assert len(result["pending_requests"]) == 1
    assert len(result["recent_actions"]) == 1
    assert len(result["objectives"]) == 1
