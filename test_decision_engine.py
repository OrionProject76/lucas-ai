# test_decision_engine.py — core/decision_engine.py
#
# ⚠️ Ce module construit le MÉCANISME de décision (lecture=auto,
# écriture=confirmation, exécution=confirmation+journalisée), pas une
# nouvelle action système réelle. Aucun test ici n'exécute quoi que ce
# soit sur la vraie machine de Cyril : `run` est toujours un callable de
# test qui incrémente un compteur, jamais un vrai volume/luminosité/
# presse-papier/lancement d'appli.

from __future__ import annotations

import pytest

from core.decision_engine import (
    DEFAULT_ACTIONS,
    ActionCategory,
    ActionDenied,
    ActionSpec,
    DecisionEngine,
)


@pytest.fixture
def engine():
    return DecisionEngine()


def _counter():
    """Callable `run` qui compte ses propres appels — pour prouver qu'une action refusée n'exécute rien."""
    calls: list[int] = []

    def _run():
        calls.append(1)
        return "fait"

    _run.calls = calls
    return _run


# ── Lecture : jamais de confirmation ─────────────────────────────────────

def test_read_action_executes_without_any_confirmation(engine) -> None:
    engine.register(ActionSpec("get_volume", ActionCategory.READ))
    run = _counter()

    result = engine.request("get_volume", run)

    assert result == "fait"
    assert run.calls == [1]


def test_read_action_works_even_without_a_confirm_callback(engine) -> None:
    """Aucun `confirm` injecté : une lecture ne doit jamais en avoir besoin."""
    assert engine.confirm is None
    engine.register(ActionSpec("get_brightness", ActionCategory.READ))
    assert engine.request("get_brightness", _counter()) == "fait"


# ── Écriture : confirmation exigée, jamais journalisée ───────────────────

def test_write_action_is_denied_by_default_without_a_confirm_callback(engine) -> None:
    """
    Sans mécanisme de confirmation injecté : refus systématique, jamais
    une autorisation par défaut — même principe que is_sensitive().
    """
    engine.register(ActionSpec("set_volume", ActionCategory.WRITE))
    run = _counter()

    with pytest.raises(ActionDenied):
        engine.request("set_volume", run)

    assert run.calls == [], "l'action refusée ne doit produire aucun effet"


def test_write_action_proceeds_when_confirmed() -> None:
    engine = DecisionEngine(confirm=lambda spec: True)
    engine.register(ActionSpec("set_brightness", ActionCategory.WRITE))
    run = _counter()

    assert engine.request("set_brightness", run) == "fait"
    assert run.calls == [1]


def test_write_action_is_denied_when_confirmation_is_refused() -> None:
    engine = DecisionEngine(confirm=lambda spec: False)
    engine.register(ActionSpec("write_clipboard", ActionCategory.WRITE))
    run = _counter()

    with pytest.raises(ActionDenied):
        engine.request("write_clipboard", run)
    assert run.calls == []


def test_write_action_is_not_logged_even_when_approved() -> None:
    """Un volume/une luminosité changés ne laissent pas de trace utile à conserver."""
    logged: list[tuple[str, str]] = []
    engine = DecisionEngine(confirm=lambda spec: True, log_event=lambda t, d="": logged.append((t, d)))
    engine.register(ActionSpec("set_volume", ActionCategory.WRITE))

    engine.request("set_volume", _counter())

    assert logged == []


# ── Exécution : confirmation exigée ET journalisée ───────────────────────

def test_execute_action_is_denied_by_default_without_confirmation(engine) -> None:
    engine.register(ActionSpec("launch_app", ActionCategory.EXECUTE))
    run = _counter()

    with pytest.raises(ActionDenied):
        engine.request("launch_app", run)
    assert run.calls == []


def test_execute_action_proceeds_and_logs_when_confirmed() -> None:
    logged: list[tuple[str, str]] = []
    engine = DecisionEngine(confirm=lambda spec: True, log_event=lambda t, d="": logged.append((t, d)))
    engine.register(ActionSpec("take_screenshot", ActionCategory.EXECUTE))

    result = engine.request("take_screenshot", _counter())

    assert result == "fait"
    assert logged == [("decision_executed", "take_screenshot")]


def test_execute_action_denied_when_confirmation_refused_is_also_logged() -> None:
    """Un refus n'est pas la même chose qu'un silence : les deux doivent apparaître en base."""
    logged: list[tuple[str, str]] = []
    engine = DecisionEngine(confirm=lambda spec: False, log_event=lambda t, d="": logged.append((t, d)))
    engine.register(ActionSpec("launch_app", ActionCategory.EXECUTE))
    run = _counter()

    with pytest.raises(ActionDenied):
        engine.request("launch_app", run)

    assert run.calls == []
    assert logged == [("decision_denied", "launch_app")]


# ── Action inconnue ───────────────────────────────────────────────────────

def test_unknown_action_is_denied(engine) -> None:
    with pytest.raises(ActionDenied, match="hors liste blanche"):
        engine.request("format_disque", _counter())


def test_unregistered_action_reports_not_requiring_confirmation_as_an_error(engine) -> None:
    with pytest.raises(ActionDenied):
        engine.requires_confirmation("inconnue")


# ── requires_confirmation() : reflète la catégorie ────────────────────────

def test_requires_confirmation_matches_the_category(engine) -> None:
    engine.register(ActionSpec("get_volume", ActionCategory.READ))
    engine.register(ActionSpec("set_volume", ActionCategory.WRITE))
    engine.register(ActionSpec("launch_app", ActionCategory.EXECUTE))

    assert engine.requires_confirmation("get_volume") is False
    assert engine.requires_confirmation("set_volume") is True
    assert engine.requires_confirmation("launch_app") is True


# ── Le contexte transmis à confirm() ──────────────────────────────────────

def test_confirm_receives_the_full_action_spec_not_just_the_name() -> None:
    """
    Une future carte d'approbation (IDEAS.md #80) doit pouvoir afficher le
    nom ET la description — pas seulement savoir qu'une confirmation est
    demandée.
    """
    received: list[ActionSpec] = []

    def _confirm(spec: ActionSpec) -> bool:
        received.append(spec)
        return True

    engine = DecisionEngine(confirm=_confirm)
    engine.register(ActionSpec("set_volume", ActionCategory.WRITE, "Changer le niveau sonore"))

    engine.request("set_volume", _counter())

    assert len(received) == 1
    assert received[0].name == "set_volume"
    assert received[0].description == "Changer le niveau sonore"


# ── get() ──────────────────────────────────────────────────────────────

def test_get_returns_none_for_an_unregistered_action(engine) -> None:
    assert engine.get("inconnue") is None


def test_get_returns_the_registered_spec(engine) -> None:
    spec = ActionSpec("get_volume", ActionCategory.READ, "Lire le niveau sonore actuel")
    engine.register(spec)
    assert engine.get("get_volume") == spec


# ── DEFAULT_ACTIONS : les exemples illustratifs du modèle attendu ─────────
#
# Aucun n'est câblé à une vraie action système (voir l'en-tête du module) —
# ces tests vérifient seulement que la catégorisation elle-même est celle
# annoncée : lecture pour consulter un réglage, écriture pour le changer,
# exécution pour lancer une appli ou capturer l'écran.

def test_default_actions_are_not_auto_registered() -> None:
    """DecisionEngine() démarre vide : à un appelant futur d'enregistrer explicitement."""
    assert DecisionEngine().get("get_volume") is None


@pytest.mark.parametrize(
    "name, expected_category",
    [
        ("get_volume", ActionCategory.READ),
        ("set_volume", ActionCategory.WRITE),
        ("get_brightness", ActionCategory.READ),
        ("set_brightness", ActionCategory.WRITE),
        ("read_clipboard", ActionCategory.READ),
        ("write_clipboard", ActionCategory.WRITE),
        ("launch_app", ActionCategory.EXECUTE),
        ("take_screenshot", ActionCategory.EXECUTE),
    ],
)
def test_default_actions_match_the_documented_model(name, expected_category) -> None:
    by_name = {spec.name: spec for spec in DEFAULT_ACTIONS}
    assert by_name[name].category == expected_category


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
