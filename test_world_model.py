# test_world_model.py — snapshot système, y compris l'horloge réelle
#
# Bug trouvé en usage réel (Cyril, 02/08/2026) : Luca's n'avait accès à
# l'heure réelle nulle part dans son contexte. Face à une question sur
# l'heure, elle inventait une valeur plausible, ou une fois recopiait un
# gabarit de placeholder issu de son propre entraînement ("il est [heure
# actuelle]") faute de vraie donnée à lire. Voir core/world_model.py.

from __future__ import annotations

import sys
from datetime import datetime as real_datetime
from types import SimpleNamespace

import pytest

from core import world_model
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


# ── _get_gpu_load() : jamais exercé qu'avec le vrai matériel ───────────
#
# get_snapshot() appelle _get_gpu_load() sans le mocker : ses branches ne
# dépendaient donc que du GPU réellement présent sur la machine qui lance
# les tests, jamais vérifiées de façon déterministe. Trouvé via mesure de
# couverture réelle, même motif que les modules security/ précédents.

def test_gpu_load_returns_the_first_gpu_load_as_a_percentage(monkeypatch) -> None:
    import GPUtil

    monkeypatch.setattr(GPUtil, "getGPUs", lambda: [SimpleNamespace(load=0.42)])
    assert world_model._get_gpu_load() == 42.0


def test_gpu_load_is_zero_without_a_dedicated_gpu(monkeypatch) -> None:
    import GPUtil

    monkeypatch.setattr(GPUtil, "getGPUs", list)
    assert world_model._get_gpu_load() == 0.0


def test_gpu_load_is_zero_when_the_driver_is_unreadable(monkeypatch) -> None:
    """Une jauge vide vaut mieux qu'un World Model en panne."""
    import GPUtil

    def _raise():
        raise RuntimeError("pilote NVIDIA absent")

    monkeypatch.setattr(GPUtil, "getGPUs", _raise)
    assert world_model._get_gpu_load() == 0.0


# ── _get_active_window_title() : jamais exercé qu'avec la vraie fenêtre ─

def test_active_window_title_reads_the_real_window(monkeypatch) -> None:
    import win32gui

    monkeypatch.setattr(win32gui, "GetForegroundWindow", lambda: 123)
    monkeypatch.setattr(win32gui, "GetWindowText", lambda hwnd: "Visual Studio Code")
    assert world_model._get_active_window_title() == "Visual Studio Code"


def test_active_window_title_falls_back_when_the_title_is_empty(monkeypatch) -> None:
    import win32gui

    monkeypatch.setattr(win32gui, "GetForegroundWindow", lambda: 123)
    monkeypatch.setattr(win32gui, "GetWindowText", lambda hwnd: "")
    assert world_model._get_active_window_title() == "Inconnu"


def test_active_window_title_reports_missing_pywin32(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "win32gui", None)
    assert world_model._get_active_window_title() == "pywin32 non installé"


def test_active_window_title_falls_back_on_any_other_error(monkeypatch) -> None:
    """Le World Model ne doit jamais faire tomber l'appelant."""
    import win32gui

    def _raise():
        raise RuntimeError("bureau verrouillé")

    monkeypatch.setattr(win32gui, "GetForegroundWindow", _raise)
    assert world_model._get_active_window_title() == "Inconnu"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
