# test_world_model.py — snapshot système, y compris l'horloge réelle
#
# Bug trouvé en usage réel (Cyril, 02/08/2026) : Luca's n'avait accès à
# l'heure réelle nulle part dans son contexte. Face à une question sur
# l'heure, elle inventait une valeur plausible, ou une fois recopiait un
# gabarit de placeholder issu de son propre entraînement ("il est [heure
# actuelle]") faute de vraie donnée à lire. Voir core/world_model.py.

from __future__ import annotations

from datetime import datetime as real_datetime

import pytest

import core.world_model as world_model
from core.world_model import format_for_prompt, get_snapshot


class _FixedDateTime:
    """Remplace datetime.now() par une valeur connue — mardi 04/08/2026."""

    _fixed = real_datetime(2026, 8, 4, 15, 30)

    @classmethod
    def now(cls):
        return cls._fixed


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr(world_model, "datetime", _FixedDateTime)


def test_snapshot_includes_the_real_local_time() -> None:
    snapshot = get_snapshot()
    assert "local_time" in snapshot
    assert "04/08/2026 15:30" in snapshot["local_time"]


def test_the_weekday_name_is_in_french_not_locale_dependent() -> None:
    """
    strftime("%A") dépend de la locale du système, qui peut rendre
    "Tuesday" au lieu de "mardi" selon la machine — un détail invisible
    en dev qui aurait fait halluciner le jour en plus de l'heure sur une
    machine mal localisée. Le nom du jour est donc construit à la main.
    """
    snapshot = get_snapshot()
    assert snapshot["local_time"].startswith("mardi")


def test_format_for_prompt_includes_the_time_locally() -> None:
    snapshot = get_snapshot()
    prompt = format_for_prompt(snapshot)
    assert "04/08/2026 15:30" in prompt
    assert "mardi" in prompt


def test_format_for_prompt_includes_the_time_even_for_the_cloud() -> None:
    """
    CPU, RAM et l'heure ne disent rien de Cyril — contrairement au titre
    de la fenêtre active, ils restent joints même vers le cloud (voir
    CLAUDE.md règle 3).
    """
    snapshot = get_snapshot()
    prompt = format_for_prompt(snapshot, include_window=False)
    assert "04/08/2026 15:30" in prompt


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
