# test_memory_weighting.py — core/memory_weighting.py
#
# Première exploitation réelle de confiance/provenance (IDEAS.md #2bis,
# socle posé le 04/08/2026 dans memory/memory_manager.py). Portée :
# ANNOTATION du contenu envoyé au LLM, pas suppression ni pondération
# numérique — un message de chat n'a pas de "poids" réglable, la seule
# façon réelle de le faire "peser moins" est de le dire explicitement.

from __future__ import annotations

import pytest

from core.memory_weighting import (
    UNCERTAIN_MARKER,
    annotate_uncertain_events,
    annotate_uncertain_history,
)
from test_memory_double import MemoryDouble


def _message(role="user", message="bonjour", confidence=1.0, expiration=None):
    return {"role": role, "message": message, "confidence": confidence, "expiration": expiration}


def _event(event_type="app_launched", details="Chrome", date="2026-08-04T10:00:00", confidence=1.0, expiration=None):
    return {
        "event_type": event_type, "details": details, "date": date,
        "confidence": confidence, "expiration": expiration,
    }


# ── Historique : le cas par défaut ne change rien ───────────────────────

def test_a_fully_confident_message_is_untouched() -> None:
    result = annotate_uncertain_history([_message(confidence=1.0)])
    assert result == [("user", "bonjour")]


def test_the_role_is_preserved_exactly() -> None:
    """Le rôle décide où le message atterrit dans le prompt (system/user/assistant) : jamais altéré."""
    result = annotate_uncertain_history([_message(role="assistant", message="voilà")])
    assert result == [("assistant", "voilà")]


# ── Faible confiance : signalé, jamais supprimé ─────────────────────────

def test_a_low_confidence_message_is_flagged() -> None:
    result = annotate_uncertain_history([_message(confidence=0.3, message="il est peut-être au bureau")])
    assert result == [("user", f"{UNCERTAIN_MARKER}il est peut-être au bureau")]


def test_the_threshold_is_configurable() -> None:
    result = annotate_uncertain_history([_message(confidence=0.5)], threshold=0.4)
    assert result == [("user", "bonjour")], "0.5 est au-dessus d'un seuil de 0.4 : pas signalé"


def test_confidence_exactly_at_the_threshold_is_not_flagged() -> None:
    """La comparaison est stricte (<) : au seuil pile, le souvenir reste digne de confiance."""
    result = annotate_uncertain_history([_message(confidence=0.6)], threshold=0.6)
    assert result == [("user", "bonjour")]


# ── Expiration ───────────────────────────────────────────────────────────

def test_an_expired_message_is_flagged_even_with_full_confidence() -> None:
    result = annotate_uncertain_history([
        _message(confidence=1.0, expiration="2020-01-01T00:00:00", message="ancien fait")
    ])
    assert result == [("user", f"{UNCERTAIN_MARKER}ancien fait")]


def test_a_future_expiration_is_not_flagged() -> None:
    result = annotate_uncertain_history([_message(expiration="2099-01-01T00:00:00")])
    assert result == [("user", "bonjour")]


def test_no_expiration_is_never_flagged_on_that_basis() -> None:
    result = annotate_uncertain_history([_message(expiration=None)])
    assert result == [("user", "bonjour")]


def test_an_unparsable_expiration_never_hides_a_memory() -> None:
    """
    Une date illisible ne doit JAMAIS, par excès de prudence, faire
    disparaître un souvenir — même principe que security/status.py.
    Ici : ne doit pas non plus faire planter l'annotation.
    """
    result = annotate_uncertain_history([_message(expiration="pas une date")])
    assert result == [("user", "bonjour")]


# ── Événements système : même logique, forme à 3 éléments ───────────────

def test_a_fully_confident_event_is_untouched() -> None:
    result = annotate_uncertain_events([_event()])
    assert result == [("app_launched", "Chrome", "2026-08-04T10:00:00")]


def test_a_low_confidence_event_is_flagged_in_its_details() -> None:
    result = annotate_uncertain_events([_event(confidence=0.2, details="RAM à 91% (mesure incertaine)")])
    assert result == [("app_launched", f"{UNCERTAIN_MARKER}RAM à 91% (mesure incertaine)", "2026-08-04T10:00:00")]


def test_the_event_type_is_never_touched() -> None:
    """format_events_for_prompt() filtre sur event_type (préfixe tts_) : il doit rester intact."""
    result = annotate_uncertain_events([_event(event_type="tts_skipped_sensitive", confidence=0.1)])
    assert result[0][0] == "tts_skipped_sensitive"


# ── Composition avec _build_messages() ──────────────────────────────────

def test_annotated_history_reaches_the_prompt(monkeypatch) -> None:
    """
    Bout en bout : un message à faible confiance dans la base doit
    apparaître signalé dans les messages envoyés au LLM, pas comme un
    fait ordinaire.
    """
    from core import lucas_core
    from core.lucas_core import LucasCore

    class _Memoire(MemoryDouble):
        def load_history_with_metadata(self):
            return [
                {
                    "role": "assistant", "message": "Cyril est probablement au bureau",
                    "confidence": 0.3, "expiration": None,
                },
                {"role": "user", "message": "question actuelle", "confidence": 1.0, "expiration": None},
            ]

        def load_history(self):
            """Utilisé par recent_context() pour le classifieur d'intention — pas ce qui est testé ici."""
            return [(e["role"], e["message"]) for e in self.load_history_with_metadata()]

        def load_recent_events_with_metadata(self, limit=5):
            return []

        def load_recent_events(self, limit=5):
            return []

    monkeypatch.setattr(lucas_core, "get_snapshot", dict)
    monkeypatch.setattr(lucas_core, "format_for_prompt", lambda s, include_window=True: "[système]")
    monkeypatch.setattr(lucas_core, "should_use_vision", lambda text, context="": False)
    monkeypatch.setattr(lucas_core, "should_use_rag", lambda text, context="": False)

    core = LucasCore.__new__(LucasCore)
    core.memory = _Memoire()  # type: ignore[assignment]  # double assume, voir test_memory_double.py
    messages = core._build_messages("question actuelle", "local")

    flagged = [m for m in messages if UNCERTAIN_MARKER in m["content"]]
    assert len(flagged) == 1
    assert "Cyril est probablement au bureau" in flagged[0]["content"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
