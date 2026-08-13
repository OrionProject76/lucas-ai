# test_daemon_subprocess.py — sous-processus du daemon : encodage et diagnostic
#
# Deux régressions à empêcher, toutes deux constatées en vrai le
# 13/08/2026 en reproduisant un `rag_indexing: failed` (ROADMAP.md §5.95) :
#
# 1. Un script qui imprime un emoji mourait dès que le daemon capturait sa
#    sortie (tube = cp1252 sur Windows, pas UTF-8). Faux échec sur un
#    travail réussi.
# 2. L'échec enregistré en base était inexploitable : la troncature gardait
#    la tête du traceback (les chemins) et jetait la queue (le type
#    d'erreur) — et un échec sans stderr s'enregistrait entièrement vide.

from __future__ import annotations

import subprocess
import sys

from lucas_daemon import child_env, subprocess_failure_summary


def _fake_result(returncode: int, stderr: str) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["python"], returncode=returncode, stdout="", stderr=stderr
    )


# ── 1. Encodage : le correctif tient sur un vrai sous-processus ────────


def test_child_env_forces_utf8() -> None:
    assert child_env()["PYTHONIOENCODING"] == "utf-8"


def test_captured_output_survives_emoji() -> None:
    """Le cas réel : un print() non-ASCII dont la sortie est capturée."""
    result = subprocess.run(
        [sys.executable, "-c", "print('\\u26a0\\ufe0f  dominance')"],
        capture_output=True, text=True, timeout=60,
        encoding="utf-8", errors="replace", env=child_env(),
        check=False,
    )
    assert result.returncode == 0, subprocess_failure_summary(result)
    assert "dominance" in result.stdout


# ── 2. Diagnostic : des faits structurels, jamais la sortie ────────────


def test_summary_keeps_exception_type_from_tail() -> None:
    """Le type est en QUEUE de traceback — c'est lui qu'on garde."""
    stderr = (
        "Traceback (most recent call last):\n"
        '  File "C:\\OrionAI\\memory\\index_documents.py", line 577, in index_directory\n'
        "    print(\n"
        "UnicodeEncodeError: 'charmap' codec can't encode characters\n"
    )
    resume = subprocess_failure_summary(_fake_result(1, stderr))
    assert resume == "returncode=1 UnicodeEncodeError"


def test_summary_handles_dotted_exception_type() -> None:
    stderr = "Traceback (most recent call last):\nrequests.exceptions.ConnectionError: refused\n"
    assert (
        subprocess_failure_summary(_fake_result(1, stderr))
        == "returncode=1 requests.exceptions.ConnectionError"
    )


def test_summary_never_leaks_paths_or_messages() -> None:
    """Un chemin, un nom de document ou un message ne doit jamais sortir."""
    stderr = (
        "Traceback (most recent call last):\n"
        '  File "C:\\OrionAI\\data\\documents\\releve_bancaire.pdf", line 1\n'
        "FileNotFoundError: releve_bancaire.pdf introuvable\n"
    )
    resume = subprocess_failure_summary(_fake_result(2, stderr))
    assert resume == "returncode=2 FileNotFoundError"
    assert "releve" not in resume
    assert "\\" not in resume and "/" not in resume


def test_summary_reports_returncode_when_stderr_empty() -> None:
    """Le cas du 13/08 : échec silencieux, plus jamais enregistré vide."""
    resume = subprocess_failure_summary(_fake_result(1, ""))
    assert resume.startswith("returncode=1")
    assert "aucune sortie d'erreur" in resume


def test_summary_reports_shape_when_no_exception_found() -> None:
    resume = subprocess_failure_summary(_fake_result(3, "erreur libre\nsans traceback\n"))
    assert resume.startswith("returncode=3")
    assert "2 lignes" in resume
    assert "erreur libre" not in resume
