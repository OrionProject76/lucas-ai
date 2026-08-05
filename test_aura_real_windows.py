# test_aura_real_windows.py — modes AURA face à de VRAIS titres de fenêtre
#
# ⚠️ Pourquoi un fichier séparé de test_aura_modes.py
# ---------------------------------------------------
# `test_aura_modes.py` teste la mécanique (précédence, commandes, état
# collant) sur des titres inventés. Ce fichier-ci teste la RECONNAISSANCE
# sur des chaînes relevées telles quelles, sans retouche.
#
# La distinction n'est pas cosmétique : le bug du 04/08/2026 (« excel » en
# sous-chaîne déclenchant WORKING sur « Wordle - The New York Times ») était
# invisible aux tests synthétiques, qui n'écrivaient que des titres
# ressemblant à ce que le code attendait. Un marqueur ne vaut que confronté
# à ce que Windows produit réellement.
#
# Les titres marqués RELEVÉ ont été capturés sur la machine de Cyril le
# 05/08/2026 (`Get-Process | Where MainWindowTitle`). Les autres suivent
# les conventions de nommage réelles des applications citées.

from __future__ import annotations

import pytest

from core.aura_modes import AuraMode, AuraModeEngine


@pytest.fixture
def engine() -> AuraModeEngine:
    return AuraModeEngine()


# ── Titres RELEVÉS sur la machine, 05/08/2026 ─────────────────────────


@pytest.mark.parametrize(
    "titre, process, attendu",
    [
        # RELEVÉ — Notepad français, tiret cadratin « – » et non « - ».
        ("*Nouveau Document texte (0).txt – Bloc-notes", "notepad", AuraMode.NONE),
        # RELEVÉ — Chrome sur une conversation Claude.
        ("Intégration HERMES au projet Luca's - Claude - Google Chrome", "chrome", AuraMode.NONE),
        # RELEVÉ — panneau de configuration Windows.
        ("Paramètres", "systemsettings", AuraMode.NONE),
    ],
)
def test_real_titles_do_not_trigger_a_mode(
    engine: AuraModeEngine, titre: str, process: str, attendu: AuraMode
) -> None:
    """
    Aucun de ces titres réels ne décrit une des 8 situations AURA. Ils
    doivent donc rendre NONE — un mode déclenché à tort change le ton de
    Luca sans raison, et c'est la façon la plus simple de rendre la
    détection agaçante plutôt qu'utile.
    """
    assert engine.detect(titre, process) is attendu


def test_a_terminal_with_a_free_form_title_is_still_working() -> None:
    """
    RELEVÉ le 05/08/2026 : le terminal de Cyril s'intitulait « ⠐ Valider
    avatar Godot et relancer serveur API ». Un terminal affiche ce que
    l'utilisateur y écrit, jamais son propre nom — aucun marqueur de TITRE
    ne pouvait donc l'attraper. C'est le cas exact qui a justifié d'ajouter
    le nom du process au snapshot.
    """
    engine = AuraModeEngine()
    titre = "⠐ Valider avatar Godot et relancer serveur API"
    assert engine.detect(titre) is AuraMode.NONE          # titre seul : aveugle
    assert engine.detect(titre, "windowsterminal") is AuraMode.WORKING


# ── Reconnaissance par titre ──────────────────────────────────────────


@pytest.mark.parametrize(
    "titre, attendu",
    [
        ("Sans titre-1 @ 100% (RVB/8) - Adobe Photoshop 2024", AuraMode.CREATING),
        ("projet_final.blend - Blender", AuraMode.CREATING),
        ("Réunion hebdo | Microsoft Teams", AuraMode.MEETING),
        ("Zoom Meeting", AuraMode.MEETING),
        ("Minecraft 1.20.4", AuraMode.GAMING),
        ("Steam", AuraMode.GAMING),
        ("Stranger Things | Netflix", AuraMode.ENTERTAINMENT),
        ("Lofi beats - YouTube - Google Chrome", AuraMode.ENTERTAINMENT),
        ("python - Stack Overflow - Google Chrome", AuraMode.LEARNING),
        ("Le tutoriel Python complet - YouTube", AuraMode.LEARNING),
        ("WhatsApp", AuraMode.SOCIAL),
        ("Cyril (2) - Messenger", AuraMode.SOCIAL),
        ("main.py - OrionAI - Visual Studio Code", AuraMode.WORKING),
    ],
)
def test_titles_map_to_the_expected_mode(
    engine: AuraModeEngine, titre: str, attendu: AuraMode
) -> None:
    assert engine.detect(titre) is attendu


# ── Reconnaissance par process (titre inutilisable) ───────────────────


@pytest.mark.parametrize(
    "process, attendu",
    [
        ("discord", AuraMode.SOCIAL),
        ("spotify", AuraMode.ENTERTAINMENT),
        ("blender", AuraMode.CREATING),
        ("zoom", AuraMode.MEETING),
        ("steam", AuraMode.GAMING),
    ],
)
def test_process_alone_is_enough(
    engine: AuraModeEngine, process: str, attendu: AuraMode
) -> None:
    """
    Le titre peut être vide ou entièrement libre — le process, lui, ne
    change pas. C'est le filet que le titre seul n'offrait pas.
    """
    assert engine.detect("", process) is attendu


def test_steamwebhelper_does_not_count_as_gaming(engine: AuraModeEngine) -> None:
    """
    `steamwebhelper` tourne en permanence dès que Steam est ouvert, même
    quand Cyril ne joue pas. C'est la raison pour laquelle les process sont
    comparés en ÉGALITÉ et non en sous-chaîne.
    """
    assert engine.detect("", "steamwebhelper") is AuraMode.NONE


# ── Faux positifs déjà payés une fois ─────────────────────────────────


@pytest.mark.parametrize(
    "titre",
    [
        "Wordle - The New York Times",   # bug réel du 04/08/2026
        "Word Search Puzzle",
        "Terminal illness support group - Google Chrome",
        "Comment installer une étagère",  # « comment » sans « faire »
    ],
)
def test_known_false_positives_stay_silent(engine: AuraModeEngine, titre: str) -> None:
    assert engine.detect(titre) is AuraMode.NONE


# ── Précédence entre modes simultanés ─────────────────────────────────


def test_meeting_beats_social(engine: AuraModeEngine) -> None:
    """Une visio en cours prime sur un Discord ouvert : quelqu'un attend."""
    assert engine.detect("Réunion hebdo | Microsoft Teams", "discord") is AuraMode.MEETING


def test_gaming_beats_entertainment(engine: AuraModeEngine) -> None:
    assert engine.detect("Minecraft 1.20.4", "spotify") is AuraMode.GAMING


def test_deep_focus_beats_everything(engine: AuraModeEngine) -> None:
    """
    Deep Focus vient d'une commande explicite de Cyril. Aucune fenêtre ne
    doit pouvoir annuler silencieusement une demande de concentration.
    """
    engine.handle_command("active le mode focus")
    assert engine.detect("Minecraft 1.20.4", "steam") is AuraMode.DEEP_FOCUS


def test_learning_override_only_applies_to_entertainment(engine: AuraModeEngine) -> None:
    """
    Le basculement « tutoriel » ne doit pas détourner un mode plus
    prioritaire : un tutoriel ouvert pendant une visio reste une visio.
    """
    assert engine.detect("tutoriel Zoom Meeting") is AuraMode.MEETING


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
