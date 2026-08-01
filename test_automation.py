# test_automation.py — liste blanche d'ouverture d'applications
#
# Remplace l'ancien contenu, qui n'était pas un test mais une démo :
# il ouvrait réellement Chrome et la calculatrice à chaque exécution.
# La version démo est conservée dans demos/demo_automation.py.
#
# subprocess.Popen est mocké : aucune application n'est lancée ici.

from __future__ import annotations

import subprocess

import pytest

from modules.automation_manager import (
    SHELL_LIKE_APPS,
    WHITELISTED_APPS,
    AutomationManager,
)


@pytest.fixture
def launcher(monkeypatch):
    """AutomationManager dont le lancement réel est intercepté."""
    launched: list[list[str]] = []
    events: list[tuple[str, str]] = []

    monkeypatch.setattr(subprocess, "Popen", lambda cmd: launched.append(cmd))
    monkeypatch.setattr("modules.automation_manager.Path.exists", lambda self: True)

    manager = AutomationManager(log_event=lambda t, d="": events.append((t, d)))
    return manager, launched, events


# ── Liste blanche ─────────────────────────────────────────────────────

def test_allowed_app_is_launched(launcher) -> None:
    manager, launched, _events = launcher
    result = manager.open_app("calculatrice")
    assert "ouverte" in result
    assert launched == [WHITELISTED_APPS["calculatrice"]]


def test_unknown_app_is_refused(launcher) -> None:
    manager, launched, _events = launcher
    assert "non autorisée" in manager.open_app("virus")
    assert launched == [], "rien ne doit être lancé"


def test_refusal_is_logged(launcher) -> None:
    """Une tentative refusée est un fait à tracer, pas un silence."""
    manager, _launched, events = launcher
    manager.open_app("virus")
    assert [t for t, _ in events] == ["automation_refused"]


@pytest.mark.parametrize("name", ["CALCULATRICE", "Calculatrice", "  calculatrice  "])
def test_app_name_is_normalized(launcher, name: str) -> None:
    """« Ouvre la Calculatrice » ne doit pas échouer sur une majuscule."""
    manager, launched, _events = launcher
    manager.open_app(name)
    assert len(launched) == 1


def test_is_allowed_matches_open_app(launcher) -> None:
    manager, _launched, _events = launcher
    assert manager.is_allowed("chrome")
    assert not manager.is_allowed("virus")


def test_list_allowed_is_sorted(launcher) -> None:
    manager, _launched, _events = launcher
    assert manager.list_allowed() == sorted(WHITELISTED_APPS)


# ── Robustesse ────────────────────────────────────────────────────────

def test_missing_executable_gives_a_useful_message(monkeypatch) -> None:
    """
    Chrome peut être installé ailleurs. Mieux vaut le dire que remonter
    un FileNotFoundError générique.
    """
    monkeypatch.setattr("modules.automation_manager.Path.exists", lambda self: False)
    result = AutomationManager().open_app("chrome")
    assert "introuvable" in result


def test_launch_failure_is_reported_not_raised(monkeypatch) -> None:
    monkeypatch.setattr("modules.automation_manager.Path.exists", lambda self: True)

    def boom(cmd):
        raise OSError("accès refusé")

    monkeypatch.setattr(subprocess, "Popen", boom)
    assert "n'a pas pu être ouverte" in AutomationManager().open_app("notepad")


def test_custom_whitelist_replaces_the_default() -> None:
    manager = AutomationManager(whitelist={"monapp": ["x.exe"]})
    assert manager.is_allowed("monapp")
    assert not manager.is_allowed("chrome")


# ── Sécurité ──────────────────────────────────────────────────────────

def test_command_is_never_built_from_user_input() -> None:
    """
    Le nom demandé sert de CLÉ dans la liste blanche, jamais de morceau
    de commande. Sans ça, « chrome & del *.* » deviendrait exécutable.
    """
    manager = AutomationManager()
    assert "non autorisée" in manager.open_app("chrome & echo pwned")


def test_no_shell_execution() -> None:
    """
    shell=True rendrait la liste blanche contournable par injection.

    Vérifié par analyse syntaxique et non par recherche de texte : le
    module documente justement pourquoi il ne l'utilise pas, et une
    simple recherche de chaîne se déclencherait sur ce commentaire.
    """
    import ast
    import inspect

    from modules import automation_manager

    tree = ast.parse(inspect.getsource(automation_manager))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "shell":
                    assert not (
                        isinstance(keyword.value, ast.Constant) and keyword.value.value
                    ), "aucun appel ne doit passer shell=True"


def test_shell_like_apps_are_logged_distinctly(launcher) -> None:
    """
    Ouvrir cmd donne accès à tout : l'événement doit être distinguable
    d'une ouverture ordinaire dans le journal (voir ROADMAP §5.1).
    """
    manager, _launched, events = launcher
    manager.open_app("cmd")
    assert [t for t, _ in events] == ["automation_shell_opened"]


def test_shell_like_set_covers_the_whitelist_entries() -> None:
    """Garde-fou : si un shell entre dans la liste, il doit être marqué."""
    known_shells = {"cmd", "powershell", "pwsh", "wscript", "cscript", "bash"}
    for app in WHITELISTED_APPS:
        if app in known_shells:
            assert app in SHELL_LIKE_APPS, f"{app} doit être marqué comme shell"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
