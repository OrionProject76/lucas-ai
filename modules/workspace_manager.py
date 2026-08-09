# modules/workspace_manager.py — Workspace Luca's (IDEAS.md #102, E-1)
#
# Rend visible ce que Luca's fait déjà : rapports produits, demandes en
# attente, actions gouvernées exécutées, objectifs en cours. Les fonctions
# de lecture (list_*/summary) restent strictement lecture seule, conforme
# au brief d'origine (cowork_workspace/BRIEF_WORKSPACE_E1.md) : "rendre
# visible", pas agir depuis cette page.
#
# Aucune donnée fabriquée (RT-2, IDEAS.md #97) : les objectifs (mémoire
# prospective) n'ont pas de champ "avancement" dans le schéma
# (memory/memory_manager.py) — on affiche leur contenu texte brut, jamais
# un pourcentage inventé.
#
# get_layout()/save_layout() (ajout 09/08/2026, demande de Cyril après
# comparatif sur maquette) font exception à la lecture seule : la
# disposition des cartes (ordre + taille) EST un état que Cyril choisit et
# qui doit survivre entre appareils/sessions — persisté côté serveur
# (table app_state existante, memory/memory_manager.py) plutôt qu'en
# localStorage navigateur, qui ne suivrait ni le passage PC/mobile ni un
# navigateur réinstallé. Rien d'autre dans ce module n'écrit quoi que ce
# soit.

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from memory import memory_manager
from modules import sandbox_manager, savings_detector

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


def get_savings_analysis() -> dict:
    """
    Analyse d'économies (B-2, cowork_workspace/BRIEF_DETECTEUR_ECONOMIES_B2_1.md)
    sur les relevés déjà importés par modules/finance_manager.py. RT-3 :
    rien ne sort de la machine, aucun appel LLM ici —
    modules/savings_detector.py est une agrégation déterministe pure.

    Import paresseux de `load_directory()`, même motif qu'`api/server.py::
    finance_summary()` : permet aux tests de monkeypatcher
    "modules.finance_manager.load_directory" directement, sans dépendre
    d'une valeur par défaut de paramètre déjà figée à l'import (piège
    documenté dans CLAUDE.md, memory/memory_manager.py, core/router.py).
    """
    from modules.finance_manager import load_directory

    manager, _skipped_files = load_directory()
    return savings_detector.analyze(manager.transactions)


def summary() -> dict:
    """
    Instantané complet pour le tableau de bord Workspace (E-1 + E-3 + B-2).

    `sandbox_runs` (E-3) et `savings` (B-2) rompent la lecture-seule
    stricte du reste de ce module UNIQUEMENT en apparence : ce module ne
    fait ici que RELIRE un état déjà écrit ailleurs (modules/
    sandbox_manager.py) ou calculé à la volée sans écriture (modules/
    savings_detector.py) — jamais proposer, exécuter ou modifier quoi que
    ce soit lui-même. Même distinction que get_layout()/save_layout() plus
    haut.
    """
    return {
        "reports": list_reports(),
        "pending_requests": list_pending_requests(),
        "recent_actions": list_recent_actions(),
        "objectives": list_objectives(),
        "sandbox_runs": sandbox_manager.list_recent(),
        "savings": get_savings_analysis(),
    }


# ── Disposition des cartes (glisser-déposer + tailles, 09/08/2026) ─────
#
# Les 4 cartes existantes sont fixes (aucune nouvelle section) — seuls
# leur ORDRE et leur TAILLE sont modifiables et persistés. Un identifiant
# de carte hors de cette liste, ou une taille hors S/M/L/XL, est refusé
# — jamais accepté silencieusement (le client pourrait sinon persister
# un état que le frontend ne sait plus rendre).

CARD_IDS = ("reports", "requests", "actions", "objectives", "sandbox", "savings")
CARD_SIZES = ("S", "M", "L", "XL")
_LAYOUT_STATE_KEY = "workspace_layout"


def _default_layout() -> dict:
    """
    "S" par défaut depuis le 09/08/2026 (compaction du Workspace, 6
    cartes) — auparavant "M". Cyril peut toujours agrandir une carte
    précise via les boutons de taille déjà existants ; ce défaut ne
    retire aucune fonction, seulement l'encombrement initial.
    """
    return {"order": list(CARD_IDS), "sizes": dict.fromkeys(CARD_IDS, "S")}


class InvalidLayout(ValueError):
    """Disposition refusée : cartes inconnues/manquantes, taille hors S/M/L/XL."""


def get_layout() -> dict:
    """
    Disposition actuelle (ordre + taille des 4 cartes), ou la disposition
    par défaut si Cyril n'a encore rien personnalisé — jamais une erreur
    ni une page vide pour un premier chargement.
    """
    memory = memory_manager.MemoryManager(db_path=memory_manager.DB_PATH)
    try:
        raw = memory.get_state(_LAYOUT_STATE_KEY)
    finally:
        memory.close()
    if raw is None:
        return _default_layout()
    try:
        layout = json.loads(raw)
    except (TypeError, ValueError):
        # Valeur corrompue/manuelle en base : retomber sur le défaut
        # plutôt que de planter la page — une disposition, contrairement
        # aux données financières, n'a rien d'assez sensible pour justifier
        # de faire échouer le chargement.
        return _default_layout()
    return layout


def save_layout(order: list, sizes: dict) -> None:
    """
    Valide puis enregistre la disposition. Lève InvalidLayout si `order`
    n'est pas exactement une permutation des 4 cartes connues, ou si une
    taille n'est pas dans CARD_SIZES — jamais un enregistrement partiel.
    """
    if sorted(order) != sorted(CARD_IDS):
        raise InvalidLayout(
            f"order doit contenir exactement {sorted(CARD_IDS)}, reçu {order!r}"
        )
    if set(sizes.keys()) != set(CARD_IDS):
        raise InvalidLayout(
            f"sizes doit couvrir exactement {sorted(CARD_IDS)}, reçu {sorted(sizes.keys())!r}"
        )
    for card_id, size in sizes.items():
        if size not in CARD_SIZES:
            raise InvalidLayout(
                f"taille inconnue pour {card_id!r} : {size!r} (attendu {CARD_SIZES})"
            )

    memory = memory_manager.MemoryManager(db_path=memory_manager.DB_PATH)
    try:
        memory.set_state(_LAYOUT_STATE_KEY, json.dumps({"order": order, "sizes": sizes}))
    finally:
        memory.close()
