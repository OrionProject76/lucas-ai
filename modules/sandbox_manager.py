# modules/sandbox_manager.py — zone sandbox du Workspace (E-3, IDEAS.md #102)
#
# Brief : cowork_workspace/BRIEF_WORKSPACE_E3_SANDBOX.md. Étape préalable du
# brief (§3, « explorer avant de construire ») : recherché dans
# modules/automation_manager.py, core/os_controller.py, core/decision_engine.py
# et par mot-clé "sandbox"/"isolat" dans tout le projet — AUCUN mécanisme
# d'exécution isolée de code n'existait avant ce module. Le seul rapport
# avec "sandbox" trouvé était la RÈGLE elle-même (VISION_LONG_TERME.md §4,
# "Aucune exécution de code auto-généré hors sandbox"), jamais implémentée.
#
# Cycle de vie d'une proposition, à la lettre du brief (§5) : le code reste
# PROPOSÉ jusqu'à décision explicite — submit() ne l'exécute JAMAIS.
#   pending --execute()--> executed   (résultat capturé, décision définitive)
#   pending --reject()-->  rejected   (jamais exécuté)
# Une proposition déjà décidée ne peut plus changer d'état : execute()/
# reject() lèvent SandboxError sur un id déjà "executed"/"rejected" — pas
# de ré-exécution silencieuse, pas de double décision.
#
# ⚠️ Isolation LOGICIELLE, pas une isolation OS — voir l'avertissement en
# tête de modules/sandbox_runner.py, qui pose les gardes réels (réseau,
# fichiers, processus). Ce module orchestre : persistance (memory_manager),
# sous-processus + timeout, jamais l'exécution elle-même.

from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

from memory import memory_manager

SANDBOX_ROOT = Path(__file__).resolve().parent.parent / "sandbox_workspace"
RUNNER_PATH = Path(__file__).resolve().parent / "sandbox_runner.py"

DEFAULT_TIMEOUT_SECONDS = 10.0
# Une sortie illimitée finirait par grossir sandbox_runs sans borne (un
# script qui boucle du print() jusqu'au timeout) — tronquer, pas retenir.
MAX_OUTPUT_CHARS = 20_000

STATUS_PENDING = "pending"
STATUS_EXECUTED = "executed"
STATUS_REJECTED = "rejected"


class SandboxError(Exception):
    """Refus explicite : proposition inconnue, code vide, ou déjà tranchée."""


def _get_or_raise(run_id: int) -> dict:
    memory = memory_manager.MemoryManager(db_path=memory_manager.DB_PATH)
    try:
        run = memory.get_sandbox_run(run_id)
    finally:
        memory.close()
    if run is None:
        raise SandboxError(f"Proposition sandbox inconnue : {run_id}")
    return run


def submit(code: str) -> dict:
    """Enregistre une proposition de code, statut 'pending'. Ne l'exécute jamais."""
    if not code.strip():
        raise SandboxError("Le code proposé est vide.")
    memory = memory_manager.MemoryManager(db_path=memory_manager.DB_PATH)
    try:
        run_id = memory.save_sandbox_run(code)
    finally:
        memory.close()
    return _get_or_raise(run_id)


def reject(run_id: int) -> dict:
    """Marque une proposition 'pending' comme rejetée — ne l'exécute jamais."""
    run = _get_or_raise(run_id)
    if run["status"] != STATUS_PENDING:
        raise SandboxError(
            f"Proposition déjà tranchée (statut actuel : {run['status']!r})."
        )
    memory = memory_manager.MemoryManager(db_path=memory_manager.DB_PATH)
    try:
        memory.update_sandbox_run(run_id, status=STATUS_REJECTED)
    finally:
        memory.close()
    return _get_or_raise(run_id)


def execute(run_id: int, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict:
    """Exécute une proposition 'pending' dans l'environnement isolé, une seule fois."""
    run = _get_or_raise(run_id)
    if run["status"] != STATUS_PENDING:
        raise SandboxError(
            f"Proposition déjà tranchée (statut actuel : {run['status']!r})."
        )

    result = _run_isolated(run["code"], timeout=timeout)

    memory = memory_manager.MemoryManager(db_path=memory_manager.DB_PATH)
    try:
        memory.update_sandbox_run(
            run_id,
            status=STATUS_EXECUTED,
            stdout=result["stdout"],
            stderr=result["stderr"],
            exit_code=result["exit_code"],
            timed_out=result["timed_out"],
        )
    finally:
        memory.close()
    return _get_or_raise(run_id)


def get(run_id: int) -> dict:
    return _get_or_raise(run_id)


def list_recent(limit: int = 20) -> list[dict]:
    memory = memory_manager.MemoryManager(db_path=memory_manager.DB_PATH)
    try:
        return memory.load_recent_sandbox_runs(limit=limit)
    finally:
        memory.close()


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n… (sortie tronquée)"


def _kill_process_tree(pid: int) -> None:
    """
    Un `python.exe` de venv sur Windows est un stub venvlauncher qui relance
    systématiquement l'interpréteur réel en PROCESS ENFANT (CLAUDE.md,
    « venv\\Scripts\\python.exe... toujours un parent, jamais l'interpréteur
    lui-même ») — tuer seulement le PID de tête laisserait cet enfant
    tourner jusqu'au timeout suivant. `/T` tue tout l'arbre sous ce PID.
    """
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            check=False,
        )
    except OSError:
        pass


def _run_isolated(code: str, *, timeout: float) -> dict:
    SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)
    script_path = SANDBOX_ROOT / f"_proposition_{uuid.uuid4().hex}.py"
    script_path.write_text(code, encoding="utf-8")

    proc = subprocess.Popen(
        # -X utf8 : force le mode UTF-8 (PEP 540) dans le sous-processus,
        # sinon stdout/stderr y encodent selon la page de code de la
        # console Windows (souvent cp1252/cp850) — un accent dans un
        # message d'erreur devient alors illisible côté parent, qui décode
        # en UTF-8 (errors="replace" masque juste le symptôme).
        [sys.executable, "-X", "utf8", str(RUNNER_PATH), str(script_path)],
        cwd=SANDBOX_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_process_tree(proc.pid)
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
        exit_code = None
        stderr = (stderr or "") + (
            f"\n[sandbox] Dépassement du délai ({timeout:.0f} s) — script interrompu."
        )

    return {
        "stdout": _truncate(stdout or ""),
        "stderr": _truncate(stderr or ""),
        "exit_code": exit_code,
        "timed_out": timed_out,
    }
