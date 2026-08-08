# test_os_controller.py — core/os_controller.py
#
# Aucun test ici ne dépend du matériel réel (audio, presse-papiers) : les
# interfaces pycaw/pyperclip sont mockées. Ce qui EST réel : le système de
# fichiers (tmp_path), et MemoryManager pour les tests de journalisation
# (même patron que test_memory_manager.py — jamais la vraie base de Cyril).

from __future__ import annotations

import pytest

from core.os_controller import (
    DestructiveActionRefused,
    OSController,
    PathNotAllowed,
)
from memory.memory_manager import MemoryManager


@pytest.fixture
def allowed_dir(tmp_path):
    d = tmp_path / "allowed"
    d.mkdir()
    return d


@pytest.fixture
def other_dir(tmp_path):
    d = tmp_path / "outside"
    d.mkdir()
    return d


@pytest.fixture
def controller(allowed_dir):
    return OSController(allowed_directories=[str(allowed_dir)])


@pytest.fixture
def memory(tmp_path):
    m = MemoryManager(db_path=tmp_path / "test_memory.db")
    yield m
    m.close()


# ── Frontières de la liste blanche de dossiers ───────────────────────────

def test_move_file_refuses_source_outside_allowed_directories(controller, allowed_dir, other_dir) -> None:
    source = other_dir / "a.txt"
    source.write_text("contenu")

    with pytest.raises(PathNotAllowed):
        controller.move_file(str(source), str(allowed_dir / "a.txt"))

    assert source.exists()  # rien n'a bougé


def test_move_file_refuses_destination_outside_allowed_directories(controller, allowed_dir, other_dir) -> None:
    source = allowed_dir / "a.txt"
    source.write_text("contenu")

    with pytest.raises(PathNotAllowed):
        controller.move_file(str(source), str(other_dir / "a.txt"))

    assert source.exists()


def test_path_traversal_is_blocked(controller, allowed_dir) -> None:
    """
    "../ailleurs.txt" depuis un dossier autorisé remonte à son PARENT, qui
    n'est pas lui-même autorisé — la résolution (Path.resolve()) doit
    l'attraper, une comparaison de préfixe de chaîne ne le ferait pas.
    """
    source = allowed_dir / "a.txt"
    source.write_text("contenu")
    escaping_destination = str(allowed_dir / ".." / "ailleurs.txt")

    with pytest.raises(PathNotAllowed):
        controller.move_file(str(source), escaping_destination)


def test_a_sibling_directory_sharing_a_name_prefix_is_not_allowed(tmp_path) -> None:
    """"Documents2" commence comme "Documents" sans y être contenu."""
    allowed = tmp_path / "Documents"
    allowed.mkdir()
    sibling = tmp_path / "Documents2"
    sibling.mkdir()
    target = sibling / "x.txt"
    target.write_text("contenu")
    controller = OSController(allowed_directories=[str(allowed)])

    with pytest.raises(PathNotAllowed):
        controller.move_file(str(target), str(allowed / "x.txt"))


# ── move_file / rename_file ──────────────────────────────────────────────

def test_move_file_moves_when_destination_does_not_exist(controller, allowed_dir) -> None:
    source = allowed_dir / "a.txt"
    source.write_text("contenu")
    subdir = allowed_dir / "sous_dossier"
    subdir.mkdir()

    controller.move_file(str(source), str(subdir / "a.txt"))

    assert (subdir / "a.txt").read_text() == "contenu"
    assert not source.exists()


def test_move_file_missing_source_raises(controller, allowed_dir) -> None:
    with pytest.raises(FileNotFoundError):
        controller.move_file(str(allowed_dir / "inexistant.txt"), str(allowed_dir / "dest.txt"))


def test_move_file_refuses_overwrite_without_confirmation(allowed_dir) -> None:
    controller = OSController(allowed_directories=[str(allowed_dir)])
    source = allowed_dir / "a.txt"
    source.write_text("nouveau")
    dest = allowed_dir / "b.txt"
    dest.write_text("ancien")

    with pytest.raises(DestructiveActionRefused):
        controller.move_file(str(source), str(dest))

    assert dest.read_text() == "ancien"
    assert source.exists()


def test_move_file_overwrites_when_confirmed(allowed_dir) -> None:
    controller = OSController(
        allowed_directories=[str(allowed_dir)], confirm_destructive=lambda message: True
    )
    source = allowed_dir / "a.txt"
    source.write_text("nouveau")
    dest = allowed_dir / "b.txt"
    dest.write_text("ancien")

    controller.move_file(str(source), str(dest))

    assert dest.read_text() == "nouveau"
    assert not source.exists()


def test_rename_file_renames_within_the_same_directory(controller, allowed_dir) -> None:
    source = allowed_dir / "a.txt"
    source.write_text("contenu")

    controller.rename_file(str(source), "b.txt")

    assert (allowed_dir / "b.txt").read_text() == "contenu"
    assert not source.exists()


def test_rename_file_refuses_overwrite_without_confirmation(allowed_dir) -> None:
    controller = OSController(allowed_directories=[str(allowed_dir)])
    source = allowed_dir / "a.txt"
    source.write_text("nouveau")
    (allowed_dir / "b.txt").write_text("ancien")

    with pytest.raises(DestructiveActionRefused):
        controller.rename_file(str(source), "b.txt")

    assert (allowed_dir / "b.txt").read_text() == "ancien"


# ── Journalisation (action_log, via MemoryManager injecté) ──────────────

def test_every_executed_action_is_logged_with_params(memory, allowed_dir) -> None:
    controller = OSController(memory=memory, allowed_directories=[str(allowed_dir)])
    source = allowed_dir / "a.txt"
    source.write_text("contenu")
    destination = allowed_dir / "b.txt"

    controller.move_file(str(source), str(destination))

    actions = memory.load_recent_actions()
    assert actions[0]["action"] == "move_file"
    assert actions[0]["source"] == "os_controller"
    assert actions[0]["result"] == "executed"
    assert actions[0]["params"] == {"source": str(source), "destination": str(destination)}


def test_denied_action_is_also_logged(memory, allowed_dir) -> None:
    controller = OSController(memory=memory, allowed_directories=[str(allowed_dir)])

    with pytest.raises(FileNotFoundError):
        controller.move_file(str(allowed_dir / "inexistant.txt"), str(allowed_dir / "dest.txt"))

    actions = memory.load_recent_actions()
    assert actions[0]["result"] == "denied"


def test_no_memory_injected_means_no_logging_but_the_action_still_runs(allowed_dir) -> None:
    controller = OSController(allowed_directories=[str(allowed_dir)])  # memory=None
    source = allowed_dir / "a.txt"
    source.write_text("contenu")

    result = controller.move_file(str(source), str(allowed_dir / "b.txt"))

    assert "déplacé" in result
    assert (allowed_dir / "b.txt").exists()


# ── Volume (pycaw mocké — jamais le matériel réel) ───────────────────────

def test_get_volume_reads_from_the_com_interface(monkeypatch, controller) -> None:
    class _FakeVolume:
        def GetMasterVolumeLevelScalar(self) -> float:
            return 0.42

    monkeypatch.setattr("core.os_controller._get_volume_interface", lambda: _FakeVolume())

    assert controller.get_volume() == 42


def test_get_volume_is_never_logged(monkeypatch, memory, allowed_dir) -> None:
    class _FakeVolume:
        def GetMasterVolumeLevelScalar(self) -> float:
            return 0.5

    monkeypatch.setattr("core.os_controller._get_volume_interface", lambda: _FakeVolume())
    controller = OSController(memory=memory, allowed_directories=[str(allowed_dir)])

    controller.get_volume()

    assert memory.load_recent_actions() == []


def test_set_volume_clamps_above_100(monkeypatch, controller) -> None:
    calls = {}

    class _FakeVolume:
        def SetMasterVolumeLevelScalar(self, value: float, _) -> None:
            calls["value"] = value

    monkeypatch.setattr("core.os_controller._get_volume_interface", lambda: _FakeVolume())

    controller.set_volume(150)

    assert calls["value"] == 1.0


def test_set_volume_clamps_below_0(monkeypatch, controller) -> None:
    calls = {}

    class _FakeVolume:
        def SetMasterVolumeLevelScalar(self, value: float, _) -> None:
            calls["value"] = value

    monkeypatch.setattr("core.os_controller._get_volume_interface", lambda: _FakeVolume())

    controller.set_volume(-10)

    assert calls["value"] == 0.0


def test_set_volume_is_logged_with_the_clamped_level(monkeypatch, memory, allowed_dir) -> None:
    class _FakeVolume:
        def SetMasterVolumeLevelScalar(self, value: float, _) -> None:
            pass

    monkeypatch.setattr("core.os_controller._get_volume_interface", lambda: _FakeVolume())
    controller = OSController(memory=memory, allowed_directories=[str(allowed_dir)])

    controller.set_volume(500)

    actions = memory.load_recent_actions()
    assert actions[0]["action"] == "set_volume"
    assert actions[0]["params"] == {"level": 100}


# ── Presse-papiers (pyperclip mocké) ─────────────────────────────────────

def test_read_clipboard_returns_the_current_content(monkeypatch, controller) -> None:
    import pyperclip

    monkeypatch.setattr(pyperclip, "paste", lambda: "contenu du presse-papiers")

    assert controller.read_clipboard() == "contenu du presse-papiers"


def test_read_clipboard_is_never_logged(monkeypatch, memory, allowed_dir) -> None:
    import pyperclip

    monkeypatch.setattr(pyperclip, "paste", lambda: "x")
    controller = OSController(memory=memory, allowed_directories=[str(allowed_dir)])

    controller.read_clipboard()

    assert memory.load_recent_actions() == []


def test_write_clipboard_calls_pyperclip_and_is_logged(monkeypatch, memory, allowed_dir) -> None:
    import pyperclip

    calls: dict[str, str] = {}
    monkeypatch.setattr(pyperclip, "copy", lambda text: calls.__setitem__("text", text))
    controller = OSController(memory=memory, allowed_directories=[str(allowed_dir)])

    controller.write_clipboard("bonjour")

    assert calls["text"] == "bonjour"
    actions = memory.load_recent_actions()
    assert actions[0]["action"] == "write_clipboard"
    assert actions[0]["params"] == {"length": 7}


# ── Capture d'écran (VisionManager mocké, jamais un second chemin) ──────

def test_take_screenshot_delegates_to_vision_manager_and_is_logged(monkeypatch, memory, allowed_dir, tmp_path) -> None:
    captured = {}

    class _FakeVisionManager:
        def capture_screen(self, output_path=None):
            captured["output_path"] = output_path
            return str(tmp_path / "screenshot.png")

    monkeypatch.setattr("modules.vision_manager.VisionManager", _FakeVisionManager)
    controller = OSController(memory=memory, allowed_directories=[str(allowed_dir)])

    result = controller.take_screenshot()

    assert result == str(tmp_path / "screenshot.png")
    actions = memory.load_recent_actions()
    assert actions[0]["action"] == "take_screenshot"
    assert actions[0]["result"] == "executed"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
