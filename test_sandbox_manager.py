# test_sandbox_manager.py — Zone sandbox du Workspace (E-3, IDEAS.md #102)
#
# SANDBOX_ROOT et memory_manager.DB_PATH sont monkeypatchés vers tmp_path
# dans CHAQUE test — jamais la vraie base ni le vrai sandbox_workspace/ du
# projet (même discipline que test_workspace_manager.py). Les tests
# d'évasion (réseau, fichiers, processus) exécutent du VRAI code dans un
# VRAI sous-processus — ce sont les gardes de modules/sandbox_runner.py qui
# sont vérifiées, pas une simulation.

from __future__ import annotations

import pytest

from memory import memory_manager
from modules import sandbox_manager


@pytest.fixture(autouse=True)
def _isolated_sandbox(monkeypatch, tmp_path):
    monkeypatch.setattr(memory_manager, "DB_PATH", tmp_path / "test_sandbox.db")
    monkeypatch.setattr(sandbox_manager, "SANDBOX_ROOT", tmp_path / "sandbox_workspace")


# ── submit() ─────────────────────────────────────────────────────────


def test_submit_creates_a_pending_run() -> None:
    run = sandbox_manager.submit("print('bonjour')")
    assert run["status"] == sandbox_manager.STATUS_PENDING
    assert run["code"] == "print('bonjour')"
    assert run["stdout"] is None
    assert run["exit_code"] is None


def test_submit_rejects_empty_code() -> None:
    with pytest.raises(sandbox_manager.SandboxError):
        sandbox_manager.submit("   \n  ")


# ── reject() ─────────────────────────────────────────────────────────


def test_reject_marks_a_pending_run_as_rejected() -> None:
    run = sandbox_manager.submit("print('jamais exécuté')")
    rejected = sandbox_manager.reject(run["id"])
    assert rejected["status"] == sandbox_manager.STATUS_REJECTED
    assert rejected["stdout"] is None  # jamais exécuté


def test_reject_refuses_an_already_decided_run() -> None:
    run = sandbox_manager.submit("print('x')")
    sandbox_manager.reject(run["id"])
    with pytest.raises(sandbox_manager.SandboxError):
        sandbox_manager.reject(run["id"])


def test_reject_refuses_an_unknown_id() -> None:
    with pytest.raises(sandbox_manager.SandboxError):
        sandbox_manager.reject(999999)


# ── execute() : cas normal ───────────────────────────────────────────


def test_execute_runs_the_code_and_captures_stdout() -> None:
    run = sandbox_manager.submit("print('bonjour depuis la sandbox')")
    result = sandbox_manager.execute(run["id"])
    assert result["status"] == sandbox_manager.STATUS_EXECUTED
    assert "bonjour depuis la sandbox" in result["stdout"]
    assert result["exit_code"] == 0
    assert result["timed_out"] is False


def test_execute_captures_a_script_error_without_crashing_the_caller() -> None:
    run = sandbox_manager.submit("raise ValueError('erreur volontaire')")
    result = sandbox_manager.execute(run["id"])
    assert result["status"] == sandbox_manager.STATUS_EXECUTED
    assert result["exit_code"] == 1
    assert "ValueError" in result["stderr"]
    assert "erreur volontaire" in result["stderr"]


def test_execute_refuses_an_already_decided_run() -> None:
    run = sandbox_manager.submit("print('x')")
    sandbox_manager.execute(run["id"])
    with pytest.raises(sandbox_manager.SandboxError):
        sandbox_manager.execute(run["id"])


def test_execute_refuses_a_rejected_run() -> None:
    run = sandbox_manager.submit("print('x')")
    sandbox_manager.reject(run["id"])
    with pytest.raises(sandbox_manager.SandboxError):
        sandbox_manager.execute(run["id"])


def test_execute_refuses_an_unknown_id() -> None:
    with pytest.raises(sandbox_manager.SandboxError):
        sandbox_manager.execute(999999)


# ── execute() : le fichier écrit dans sandbox_workspace/ existe vraiment ──


def test_execute_can_write_a_file_inside_sandbox_workspace() -> None:
    run = sandbox_manager.submit(
        "with open('resultat.txt', 'w', encoding='utf-8') as f:\n"
        "    f.write('ok')\n"
        "print('écrit')\n"
    )
    result = sandbox_manager.execute(run["id"])
    assert result["exit_code"] == 0
    written = sandbox_manager.SANDBOX_ROOT / "resultat.txt"
    assert written.read_text(encoding="utf-8") == "ok"


# ── Garde réseau ─────────────────────────────────────────────────────


def test_execute_blocks_network_access() -> None:
    run = sandbox_manager.submit(
        "import socket\ns = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
    )
    result = sandbox_manager.execute(run["id"])
    assert result["exit_code"] == 1
    assert "PermissionError" in result["stderr"]
    assert "réseau" in result["stderr"]


# ── Garde fichiers : écriture hors sandbox_workspace/ ───────────────


def test_execute_blocks_writing_outside_sandbox_workspace(tmp_path) -> None:
    outside = tmp_path / "hors_sandbox" / "cible.txt"
    outside.parent.mkdir(parents=True, exist_ok=True)
    run = sandbox_manager.submit(
        f"open(r{str(outside)!r}, 'w', encoding='utf-8').write('ne devrait jamais exister')\n"
    )
    result = sandbox_manager.execute(run["id"])
    assert result["exit_code"] == 1
    assert "PermissionError" in result["stderr"]
    assert not outside.exists()


def test_execute_blocks_deleting_a_file_outside_sandbox_workspace(tmp_path) -> None:
    outside = tmp_path / "hors_sandbox" / "important.txt"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text("ne doit jamais être supprimé", encoding="utf-8")
    run = sandbox_manager.submit(f"import os\nos.remove(r{str(outside)!r})\n")
    result = sandbox_manager.execute(run["id"])
    assert result["exit_code"] == 1
    assert "PermissionError" in result["stderr"]
    assert outside.exists()


def test_execute_blocks_pathlib_unlink_outside_sandbox_workspace(tmp_path) -> None:
    """
    Vérifie que le patch os.unlink protège aussi pathlib.Path.unlink() —
    pathlib délègue à os.unlink() au moment de l'appel, pas à une copie
    figée à l'import, donc le patch posé dans sandbox_runner.py s'applique
    aussi ici. Test explicite plutôt que supposé : c'est un détail
    d'implémentation de CPython, pas un contrat documenté.
    """
    outside = tmp_path / "hors_sandbox" / "important.txt"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text("ne doit jamais être supprimé", encoding="utf-8")
    run = sandbox_manager.submit(
        f"from pathlib import Path\nPath(r{str(outside)!r}).unlink()\n"
    )
    result = sandbox_manager.execute(run["id"])
    assert result["exit_code"] == 1
    assert outside.exists()


# ── Garde processus ──────────────────────────────────────────────────


def test_execute_blocks_spawning_an_external_process() -> None:
    run = sandbox_manager.submit(
        "import subprocess\nsubprocess.Popen(['cmd', '/c', 'echo devrait etre bloque'])\n"
    )
    result = sandbox_manager.execute(run["id"])
    assert result["exit_code"] == 1
    assert "PermissionError" in result["stderr"]


# ── Timeout ───────────────────────────────────────────────────────────


def test_execute_kills_a_script_that_runs_too_long() -> None:
    run = sandbox_manager.submit("import time\ntime.sleep(30)\n")
    result = sandbox_manager.execute(run["id"], timeout=1.5)
    assert result["status"] == sandbox_manager.STATUS_EXECUTED
    assert result["timed_out"] is True
    assert result["exit_code"] is None


# ── get() / list_recent() ────────────────────────────────────────────


def test_get_returns_the_current_state_of_a_run() -> None:
    run = sandbox_manager.submit("print('x')")
    assert sandbox_manager.get(run["id"])["id"] == run["id"]


def test_get_refuses_an_unknown_id() -> None:
    with pytest.raises(sandbox_manager.SandboxError):
        sandbox_manager.get(999999)


def test_list_recent_returns_empty_list_when_nothing_submitted() -> None:
    assert sandbox_manager.list_recent() == []


def test_list_recent_returns_newest_first() -> None:
    first = sandbox_manager.submit("print(1)")
    second = sandbox_manager.submit("print(2)")
    runs = sandbox_manager.list_recent()
    assert [r["id"] for r in runs] == [second["id"], first["id"]]
