# test_vram_watchdog.py — modules/vram_watchdog.py
#
# Aucun appel système réel : GPUtil, tasklist, taskkill et l'écriture en
# base sont tous monkeypatchés. Le test de charge réelle (forcer la
# VRAM et vérifier la bascule) est fait manuellement en session, pas
# ici — voir cowork_workspace/SESSION_LOG_2026-08-07.md.

from __future__ import annotations

import modules.vram_watchdog as vw


class _FakeGPU:
    def __init__(self, memory_free: float) -> None:
        self.memoryFree = memory_free


def _patch_gpu(monkeypatch, free_mb):
    class _FakeGPUtil:
        @staticmethod
        def getGPUs():
            return [_FakeGPU(free_mb)]

    monkeypatch.setitem(__import__("sys").modules, "GPUtil", _FakeGPUtil)


def _patch_events(monkeypatch):
    events = []
    monkeypatch.setattr(
        vw, "save_event_from_any_thread",
        lambda event_type, details="": events.append((event_type, details)) or True,
    )
    return events


def test_get_free_vram_mb_rend_none_sans_gpu(monkeypatch):
    class _FakeGPUtilVide:
        @staticmethod
        def getGPUs():
            return []

    monkeypatch.setitem(__import__("sys").modules, "GPUtil", _FakeGPUtilVide)
    assert vw.get_free_vram_mb() is None


def test_get_free_vram_mb_rend_none_si_gputil_leve(monkeypatch):
    class _FakeGPUtilCasse:
        @staticmethod
        def getGPUs():
            raise RuntimeError("pilote absent")

    monkeypatch.setitem(__import__("sys").modules, "GPUtil", _FakeGPUtilCasse)
    assert vw.get_free_vram_mb() is None


def test_sous_le_seuil_arrete_lucas3d_et_journalise(monkeypatch):
    _patch_gpu(monkeypatch, free_mb=300.0)
    events = _patch_events(monkeypatch)
    monkeypatch.setattr(vw, "is_lucas3d_running", lambda: True)
    stopped = {"called": False}
    monkeypatch.setattr(vw, "stop_lucas3d", lambda: stopped.__setitem__("called", True) or True)

    watchdog = vw.VramWatchdog(threshold_mb=1536, poll_seconds=999)
    watchdog.check_once()

    assert stopped["called"] is True
    assert watchdog.in_fallback is True
    assert events and events[0][0] == "vram_watchdog_fallback"
    assert "300" in events[0][1]


def test_sous_le_seuil_sans_lucas3d_actif_ne_journalise_rien(monkeypatch):
    _patch_gpu(monkeypatch, free_mb=300.0)
    events = _patch_events(monkeypatch)
    monkeypatch.setattr(vw, "is_lucas3d_running", lambda: False)
    monkeypatch.setattr(vw, "stop_lucas3d", lambda: (_ for _ in ()).throw(
        AssertionError("stop_lucas3d ne doit pas être appelé si rien ne tourne")
    ))

    watchdog = vw.VramWatchdog(threshold_mb=1536, poll_seconds=999)
    watchdog.check_once()

    assert watchdog.in_fallback is False
    assert events == []


def test_ne_journalise_pas_deux_fois_de_suite_sous_le_seuil(monkeypatch):
    """Une fois en repli, un second passage sous le seuil ne rappelle pas stop_lucas3d."""
    _patch_gpu(monkeypatch, free_mb=300.0)
    events = _patch_events(monkeypatch)
    calls = {"stop": 0}
    monkeypatch.setattr(vw, "is_lucas3d_running", lambda: True)
    monkeypatch.setattr(vw, "stop_lucas3d", lambda: calls.__setitem__("stop", calls["stop"] + 1) or True)

    watchdog = vw.VramWatchdog(threshold_mb=1536, poll_seconds=999)
    watchdog.check_once()
    watchdog.check_once()

    assert calls["stop"] == 1
    assert len(events) == 1


def test_retour_au_dessus_du_seuil_journalise_la_restauration(monkeypatch):
    events = _patch_events(monkeypatch)
    monkeypatch.setattr(vw, "is_lucas3d_running", lambda: True)
    monkeypatch.setattr(vw, "stop_lucas3d", lambda: True)

    watchdog = vw.VramWatchdog(threshold_mb=1536, poll_seconds=999)
    watchdog.in_fallback = True  # déjà en repli d'un cycle précédent

    _patch_gpu(monkeypatch, free_mb=2000.0)
    watchdog.check_once()

    assert watchdog.in_fallback is False
    assert events and events[0][0] == "vram_watchdog_restore"
    assert "2000" in events[0][1]


def test_au_dessus_du_seuil_hors_repli_ne_fait_rien(monkeypatch):
    _patch_gpu(monkeypatch, free_mb=5000.0)
    events = _patch_events(monkeypatch)
    monkeypatch.setattr(vw, "is_lucas3d_running", lambda: False)

    watchdog = vw.VramWatchdog(threshold_mb=1536, poll_seconds=999)
    watchdog.check_once()

    assert watchdog.in_fallback is False
    assert events == []
