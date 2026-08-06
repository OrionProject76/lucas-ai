# test_presence_context.py — le bloc [Contexte] de présence
#
# Matière première de la variation de ton (ROADMAP.md §5.32). Ces
# branches n'étaient couvertes par aucun test : les doubles rendaient
# tous `None` pour `minutes_since_last_exchange`, donc une seule des
# quatre branches était jamais exécutée.
#
# ⚠️ Deux propriétés comptent autant que le contenu :
#   - une chaîne VIDE quand il n'y a rien à dire (diluer le prompt est un
#     risque mesuré ici, §5.29) ;
#   - AUCUNE forme d'adresse dans le texte injecté — un bloc au service du
#     tutoiement qui écrirait « vous » modéliserait ce qu'il combat.

from __future__ import annotations

import pytest

from core import lucas_core
from core.lucas_core import LucasCore
from test_memory_double import MemoryDouble


def _core(minutes):
    class _Memoire(MemoryDouble):
        def minutes_since_last_exchange(self):
            return minutes

    instance = LucasCore.__new__(LucasCore)
    instance.memory = _Memoire()  # type: ignore[assignment]  # double assume, voir test_memory_double.py
    return instance


# ── Les quatre branches de présence ───────────────────────────────────


def test_no_previous_exchange_is_stated(monkeypatch) -> None:
    assert "Premier échange" in _core(None)._describe_presence({})


def test_a_recent_exchange_is_stated() -> None:
    assert "déjà en cours" in _core(3)._describe_presence({})


def test_a_long_gap_is_stated() -> None:
    assert "douze heures" in _core(800)._describe_presence({})


def test_the_middle_range_says_nothing() -> None:
    """
    Entre 10 minutes et 12 heures, il n'y a rien d'intéressant à dire.
    Injecter « dernier échange il y a 3 h 12 » n'aiderait pas le modèle à
    choisir un ton et allongerait le prompt pour rien.
    """
    assert _core(200)._describe_presence({}) == ""


# ── Le mode AURA s'ajoute au même bloc ────────────────────────────────


def test_the_aura_mode_reaches_the_block() -> None:
    bloc = _core(200)._describe_presence({"active_window": "main.py - Visual Studio Code"})
    assert "travaille" in bloc


def test_mode_and_presence_are_combined() -> None:
    bloc = _core(3)._describe_presence({"active_window": "Classeur1 - Excel"})
    assert "travaille" in bloc
    assert "déjà en cours" in bloc


def test_the_process_is_used_when_the_title_says_nothing() -> None:
    """
    Le terminal réel de Cyril s'intitulait « ⠐ Valider avatar Godot… ».
    Sans le nom du process, ce bloc resterait aveugle (§5.34).
    """
    bloc = _core(200)._describe_presence(
        {"active_window": "⠐ Valider avatar Godot", "active_process": "windowsterminal"}
    )
    assert "travaille" in bloc


# ── Les deux propriétés structurelles ─────────────────────────────────


def test_nothing_to_say_produces_an_empty_string() -> None:
    """
    Pas « [Contexte : rien à signaler] ». Une ligne qui n'apprend rien
    dilue le prompt système, et la dilution est un risque mesuré ici :
    une règle passe de 9/9 à 2/9 sous historique long (§5.29).
    """
    assert _core(200)._describe_presence({"active_window": "Paramètres"}) == ""


@pytest.mark.parametrize("minutes", [None, 3, 800, 200])
@pytest.mark.parametrize(
    "fenetre", ["main.py - Visual Studio Code", "Minecraft 1.20.4", "Paramètres"]
)
def test_the_block_never_uses_a_form_of_address(minutes, fenetre) -> None:
    """
    Régression réelle : la première version écrivait « C'est VOTRE premier
    échange » — un bloc au service du tutoiement qui modélisait du
    vouvoiement, deux lignes au-dessus de la règle qui l'interdit.
    """
    bloc = _core(minutes)._describe_presence({"active_window": fenetre}).lower()
    for forme in (" vous ", " votre ", " vos ", " tu ", " ton ", " tes "):
        assert forme not in bloc, f"{forme!r} ne doit pas apparaître dans {bloc!r}"


def test_the_block_is_never_sent_to_the_cloud(monkeypatch) -> None:
    """
    Le mode se déduit du titre de la fenêtre active, qui ne sort jamais de
    la machine (CLAUDE.md règle 3). Un mode « Working » déduit de
    « impots_2025.pdf » raconte la même chose que le titre lui-même.
    """
    monkeypatch.setattr(lucas_core, "get_snapshot", lambda: {"active_window": "Classeur1 - Excel"})
    monkeypatch.setattr(
        lucas_core, "format_for_prompt", lambda snapshot, include_window=True: "[système]"
    )
    core = _core(3)
    messages = core._build_messages("bonjour", "cloud")
    assert not any("[Contexte :" in m["content"] for m in messages)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
