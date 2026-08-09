# test_capability_registry.py — Poste de Commandement IA (E-5)

from __future__ import annotations

import config
from modules import capability_registry as registry


def test_returns_a_non_empty_list_of_capabilities() -> None:
    capabilities = registry.list_capabilities()
    assert len(capabilities) > 0
    assert all(isinstance(c, registry.Capability) for c in capabilities)


def test_every_capability_has_a_non_empty_name_category_and_description() -> None:
    for c in registry.list_capabilities():
        assert c.name.strip()
        assert c.category.strip()
        assert c.description.strip()
        assert c.status.strip()


def test_capability_names_are_unique() -> None:
    names = [c.name for c in registry.list_capabilities()]
    assert len(names) == len(set(names))


def test_excludes_the_orphan_stt_manager_flagged_by_the_cleanup_audit() -> None:
    """
    modules/stt_manager.py est identifié comme orphelin par l'audit du
    09/08/2026 (cowork_workspace/reports/Audit_Nettoyage_LucasAI_2026-08-09.md)
    — ne doit jamais apparaître ici comme une capacité active.
    """
    for c in registry.list_capabilities():
        assert "stt_manager" not in c.detail.lower()
        assert "stt_manager" not in c.name.lower()


def test_os_controller_is_marked_built_but_not_wired() -> None:
    """
    Vérifié par exploration (aucun import de core/os_controller.py hors
    de son propre test) : ne doit jamais être présenté comme "actif".
    """
    os_controller = next(c for c in registry.list_capabilities() if "OS Controller" in c.name)
    assert os_controller.status == registry.STATUS_BUILT_NOT_WIRED


def test_vram_watchdog_is_marked_manual() -> None:
    watchdog = next(c for c in registry.list_capabilities() if "VRAM" in c.name)
    assert watchdog.status == registry.STATUS_MANUAL


def test_vlm_status_reflects_the_real_config_flag(monkeypatch) -> None:
    monkeypatch.setattr(config, "VLM_ENABLED", False)
    vlm = next(c for c in registry.list_capabilities() if "VLM" in c.name)
    assert vlm.status == registry.STATUS_DISABLED

    monkeypatch.setattr(config, "VLM_ENABLED", True)
    vlm = next(c for c in registry.list_capabilities() if "VLM" in c.name)
    assert vlm.status == registry.STATUS_ACTIVE


def test_reasoning_engine_status_reflects_the_real_config_flag(monkeypatch) -> None:
    monkeypatch.setattr(config, "REASONING_ENGINE_ENABLED", False)
    reasoning = next(c for c in registry.list_capabilities() if "chaîne" in c.name)
    assert reasoning.status == registry.STATUS_DISABLED

    monkeypatch.setattr(config, "REASONING_ENGINE_ENABLED", True)
    reasoning = next(c for c in registry.list_capabilities() if "chaîne" in c.name)
    assert reasoning.status == registry.STATUS_ACTIVE


def test_ocr_status_reflects_the_real_config_flag(monkeypatch) -> None:
    monkeypatch.setattr(config, "OCR_ENABLED", False)
    ocr = next(c for c in registry.list_capabilities() if "OCR" in c.name)
    assert ocr.status == registry.STATUS_DISABLED
