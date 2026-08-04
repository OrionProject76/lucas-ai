# test_aura_modes.py — core/aura_modes.py
#
# MVP réduit (session autonome 04/08/2026) : Working et Deep Focus
# seulement, sur les 8 modes catalogués dans IDEAS.md §3. Détection
# déterministe uniquement — aucun test ici ne vérifie de "comportement"
# (notifications, musique, compte à rebours) : ces actions système
# n'existent pas encore et ne sont pas construites dans ce module.

from __future__ import annotations

import pytest

from core.aura_modes import AuraMode, AuraModeChange, AuraModeEngine


@pytest.fixture
def engine():
    return AuraModeEngine()


# ── Working : déduit de la fenêtre active ────────────────────────────

def test_working_is_detected_from_a_professional_app(engine) -> None:
    assert engine.detect("main.py - Visual Studio Code") == AuraMode.WORKING


@pytest.mark.parametrize(
    "window_title",
    [
        "Budget2026.xlsx - Excel",
        "Rapport - Word",
        "PowerShell",
        "main.py - PyCharm",
    ],
)
def test_working_is_detected_for_various_professional_apps(engine, window_title) -> None:
    assert engine.detect(window_title) == AuraMode.WORKING


def test_no_mode_for_an_unrelated_window(engine) -> None:
    assert engine.detect("YouTube - Google Chrome") == AuraMode.NONE


def test_no_mode_for_an_empty_window_title(engine) -> None:
    assert engine.detect("") == AuraMode.NONE


def test_detection_is_case_insensitive(engine) -> None:
    assert engine.detect("BUDGET.XLSX - EXCEL") == AuraMode.WORKING


# ── Faux positifs — trouvés le 04/08/2026 sur des titres réels et
# courants sans rapport avec du travail (audit "validation contre le
# vrai service" étendu aux modes AURA). "excel"/"word"/"terminal" en
# sous-chaîne nue matchaient des titres de jeux, d'articles et de sites
# web réels, pas seulement des cas construits pour l'occasion.
@pytest.mark.parametrize(
    "window_title",
    [
        "Wordle - The New York Times - Mozilla Firefox",
        "Word Search Puzzle - jeu gratuit - Google Chrome",
        "Terminal illness support group - Reddit",
        "Excel dans la vie - blog motivation - Google Chrome",
    ],
)
def test_single_word_markers_do_not_false_positive_on_real_titles(engine, window_title) -> None:
    assert engine.detect(window_title) == AuraMode.NONE


def test_windows_terminal_app_is_still_detected(engine) -> None:
    """Le retrait de "terminal" nu ne doit pas perdre la vraie appli moderne."""
    assert engine.detect("Windows Terminal") == AuraMode.WORKING


# ── Deep Focus : uniquement sur commande explicite ───────────────────

def test_deep_focus_is_never_inferred_from_a_window(engine) -> None:
    """
    Aucune fenêtre, même professionnelle, ne doit activer Deep Focus
    toute seule : bloquer les notifications sur une inférence fragile
    serait pire que ne rien bloquer.
    """
    assert engine.detect("main.py - Visual Studio Code") == AuraMode.WORKING


def test_an_explicit_command_activates_deep_focus(engine) -> None:
    change = engine.handle_command("active le mode focus")
    assert change == AuraModeChange(AuraMode.DEEP_FOCUS, "commande explicite")


def test_deep_focus_stays_active_regardless_of_the_window_afterwards(engine) -> None:
    """
    Le seul mode "collant" : une fois activé, il ne doit pas être annulé
    silencieusement par un simple changement de fenêtre.
    """
    engine.handle_command("concentre-toi")
    assert engine.detect("YouTube - Google Chrome") == AuraMode.DEEP_FOCUS
    assert engine.detect("main.py - Visual Studio Code") == AuraMode.DEEP_FOCUS


def test_an_explicit_command_deactivates_deep_focus(engine) -> None:
    engine.handle_command("active le mode focus")
    change = engine.handle_command("désactive le mode focus")

    assert change == AuraModeChange(AuraMode.NONE, "commande explicite")
    assert engine.detect("YouTube - Google Chrome") == AuraMode.NONE


def test_deactivating_deep_focus_lets_working_resume(engine) -> None:
    engine.handle_command("mode deep focus")
    engine.handle_command("fin du focus")

    assert engine.detect("main.py - Visual Studio Code") == AuraMode.WORKING


def test_an_unrelated_sentence_does_not_change_anything(engine) -> None:
    assert engine.handle_command("quel temps fait-il ?") is None
    assert engine.detect("YouTube - Google Chrome") == AuraMode.NONE


def test_command_matching_is_case_insensitive(engine) -> None:
    change = engine.handle_command("ACTIVE LE MODE FOCUS")
    assert change is not None
    assert change.mode == AuraMode.DEEP_FOCUS


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
