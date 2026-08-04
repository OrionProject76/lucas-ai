# core/memory_weighting.py — exploite confiance/provenance (IDEAS.md #2bis)
#
# ⚠️ Le socle (memory/memory_manager.py, session du 04/08/2026) ajoutait
# les colonnes mais rien ne s'en servait. Ce module est la première
# exploitation réelle.
#
# ── Portée : ANNOTATION, pas suppression ni pondération numérique ──────
#
# Un message envoyé à un LLM n'a pas de "poids" au sens mathématique — il
# n'existe pas de bouton pour lui faire compter un tour d'historique à
# 40% plutôt qu'à 100%. La seule façon RÉELLE de faire "peser moins" un
# souvenir peu fiable est de le DIRE explicitement au modèle. Même
# principe que le RAG sans résultat ou le refus de vision
# (core/lucas_core.py) : ne jamais laisser deviner ce qu'on peut vérifier
# — ici, qu'un souvenir est incertain plutôt que de le présenter à égalité
# avec un fait récent et validé.
#
# ── Où c'est branché, où ça ne l'est pas ────────────────────────────────
#
# Branché dans core/lucas_core.py::_build_messages(), à la toute première
# étape (avant SOURCE_HISTORY_MESSAGES, CLOUD_HISTORY_MESSAGES,
# is_vision_refusal(), fit_history_to_budget()) — qui continuent tous de
# recevoir des tuples (role, content) / (event_type, details, date)
# ordinaires, strictement inchangés. Deux points d'entrée :
#   - annotate_uncertain_history() : self.memory.load_history_with_metadata()
#   - annotate_uncertain_events()  : self.memory.load_recent_events_with_metadata()
#
# PAS branché sur le RAG (modules/rag_manager.py) : les documents RAG
# vivent dans ChromaDB avec un schéma de métadonnées différent (source,
# chunk, sha, periods) qui n'a jamais eu de colonne confidence/expiration
# — IDEAS.md #2bis parlait explicitement de "la table memories/events
# SQLite existante", pas de ChromaDB. Étendre le RAG serait un chantier
# différent, non demandé ici.
#
# PAS branché sur le Reasoning Engine — REASONING_ENGINE_ENABLED reste
# False (décision de Cyril), non touché.
#
# ── Pourquoi c'est un no-op aujourd'hui, et c'est attendu ───────────────
#
# save_message()/save_event() par défaut : confidence=1.0, pas
# d'expiration. Aucun appelant du projet ne passe autre chose aujourd'hui
# — cette fonction n'annote donc RIEN sur la base réelle de Cyril tant
# que rien n'écrit une confiance plus basse. C'est le socle prêt pour le
# jour où une source moins fiable (ex. une inférence WebModel non
# confirmée) écrira avec une confiance réduite.

from __future__ import annotations

from datetime import datetime

from config import MEMORY_CONFIDENCE_THRESHOLD

UNCERTAIN_MARKER = (
    "[Souvenir incertain — confiance faible ou périmé, à ne PAS traiter "
    "comme un fait établi] "
)


def _is_expired(expiration: str | None) -> bool:
    """
    True si `expiration` est une date passée. Une valeur absente ou
    illisible n'est JAMAIS considérée expirée — même principe que
    security/status.py::_is_active() : une donnée qu'on ne sait pas lire
    ne doit jamais, par excès de zèle, faire disparaître un souvenir.
    """
    if not expiration:
        return False
    try:
        return datetime.fromisoformat(expiration) < datetime.now()
    except ValueError:
        return False


def _is_uncertain(entry: dict, threshold: float) -> bool:
    return entry["confidence"] < threshold or _is_expired(entry.get("expiration"))


def annotate_uncertain_history(
    entries: list[dict],
    threshold: float = MEMORY_CONFIDENCE_THRESHOLD,
) -> list[tuple[str, str]]:
    """
    `load_history_with_metadata()` -> tuples (role, content), même forme
    que `load_history()` : un remplacement direct dans
    `_build_messages()`, sans toucher à ce qui consomme le résultat
    ensuite.
    """
    result = []
    for entry in entries:
        content = entry["message"]
        if _is_uncertain(entry, threshold):
            content = f"{UNCERTAIN_MARKER}{content}"
        result.append((entry["role"], content))
    return result


def annotate_uncertain_events(
    entries: list[dict],
    threshold: float = MEMORY_CONFIDENCE_THRESHOLD,
) -> list[tuple[str, str, str]]:
    """
    `load_recent_events_with_metadata()` -> tuples (event_type, details,
    date), même forme que `load_recent_events()` : un remplacement
    direct, `format_events_for_prompt()` ne change pas.
    """
    result = []
    for entry in entries:
        details = entry["details"]
        if _is_uncertain(entry, threshold):
            details = f"{UNCERTAIN_MARKER}{details}"
        result.append((entry["event_type"], details, entry["date"]))
    return result
