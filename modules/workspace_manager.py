# modules/workspace_manager.py — Workspace Luca's (IDEAS.md #102, E-1)
#
# Rend visible ce que Luca's fait déjà : rapports produits, demandes en
# attente, actions gouvernées exécutées, objectifs en cours. Lecture seule
# stricte — aucune fonction ici n'écrit quoi que ce soit, conformément au
# brief (cowork_workspace/BRIEF_WORKSPACE_E1.md) : "rendre visible", pas
# agir depuis cette page.
#
# Aucune donnée fabriquée (RT-2, IDEAS.md #97) : les objectifs (mémoire
# prospective) n'ont pas de champ "avancement" dans le schéma
# (memory/memory_manager.py) — on affiche leur contenu texte brut, jamais
# un pourcentage inventé.

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from memory import memory_manager

COWORK_DIR = Path(__file__).resolve().parent.parent / "cowork_workspace"
REPORTS_DIR = COWORK_DIR / "reports"
REQUESTS_DIR = COWORK_DIR / "requests"

_TITLE_PATTERN = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _extract_title(path: Path) -> str:
    """Premier titre Markdown `# ...` du fichier, ou son nom si absent/illisible/non-Markdown."""
    if path.suffix.lower() != ".md":
        return path.stem
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return path.stem
    match = _TITLE_PATTERN.search(text)
    return match.group(1).strip() if match else path.stem


def _file_entry(path: Path) -> dict:
    stat = path.stat()
    return {
        "filename": path.name,
        "title": _extract_title(path),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
    }


def list_reports() -> list[dict]:
    """Rapports produits dans cowork_workspace/reports/, les plus récents en premier."""
    if not REPORTS_DIR.is_dir():
        return []
    entries = [_file_entry(p) for p in REPORTS_DIR.iterdir() if p.is_file()]
    return sorted(entries, key=lambda e: e["modified_at"], reverse=True)


def list_pending_requests() -> list[dict]:
    """
    Demandes en attente de traitement : fichiers de cowork_workspace/requests/
    sans suffixe `_DONE`. `README.md` exclu — c'est un guide, pas une demande
    (voir cowork_workspace/requests/README.md).
    """
    if not REQUESTS_DIR.is_dir():
        return []
    entries = [
        _file_entry(p)
        for p in REQUESTS_DIR.iterdir()
        if p.is_file() and p.name != "README.md" and "_DONE" not in p.stem
    ]
    return sorted(entries, key=lambda e: e["modified_at"], reverse=True)


def list_recent_actions(limit: int = 20) -> list[dict]:
    """
    Actions récentes gouvernées par core/decision_engine.py (action_log,
    Brique 2) — pas une todo-list, un journal de décisions déjà exécutées
    ou refusées.

    db_path=memory_manager.DB_PATH explicite, jamais MemoryManager() nu :
    même piège documenté dans core/router.py et
    memory_manager.save_event_from_any_thread — le défaut de paramètre de
    __init__ est figé à la définition de la fonction, un monkeypatch de
    DB_PATH dans un test ne l'atteindrait jamais autrement.
    """
    memory = memory_manager.MemoryManager(db_path=memory_manager.DB_PATH)
    try:
        return memory.load_recent_actions(limit=limit)
    finally:
        memory.close()


def list_objectives(limit: int = 20) -> list[dict]:
    """Objectifs en cours (mémoire prospective, Brique 3) — lecture seule."""
    memory = memory_manager.MemoryManager(db_path=memory_manager.DB_PATH)
    try:
        return memory.recall(memory_type="prospective", limit=limit)
    finally:
        memory.close()


def summary() -> dict:
    """Instantané complet pour le tableau de bord Workspace (E-1)."""
    return {
        "reports": list_reports(),
        "pending_requests": list_pending_requests(),
        "recent_actions": list_recent_actions(),
        "objectives": list_objectives(),
    }
