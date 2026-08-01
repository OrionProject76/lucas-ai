# test_avatar.py — les 5 modes de présence
#
# L'avatar n'est pas décoratif : il indique ce que Luca's est en train de
# faire. WATCHING en particulier sert de témoin de capture d'écran, comme
# la LED d'une webcam — s'il ne s'allume pas, Cyril ne sait pas que son
# écran est lu.
#
# Qt tourne en mode « offscreen » : aucune fenêtre ne s'ouvre.

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from ui.avatar_widget import (
    IDLE,
    INACTIVE_STATES,
    LISTENING,
    PRESENCE_STATES,
    SPEAKING,
    THINKING,
    WATCHING,
    AvatarWidget,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def avatar(app):
    widget = AvatarWidget()
    yield widget
    widget.anim_timer.stop()
    widget.blink_timer_obj.stop()


# ── Les cinq modes ────────────────────────────────────────────────────

def test_there_are_exactly_five_presence_states() -> None:
    assert len(PRESENCE_STATES) == 5


def test_listening_is_declared_inactive() -> None:
    """
    Le PC n'a pas de micro (IDEAS.md #69) : LISTENING est prévu mais
    inatteignable jusqu'au pont mobile. Le déclarer évite de croire à
    cinq modes opérationnels alors qu'il y en a quatre.
    """
    assert LISTENING in INACTIVE_STATES
    assert set(INACTIVE_STATES) < set(PRESENCE_STATES)


@pytest.mark.parametrize("state", PRESENCE_STATES)
def test_every_state_renders_without_error(avatar, state: str) -> None:
    avatar.set_state(state)
    avatar.update_animation()
    avatar.repaint()
    assert avatar.state == state


# ── Robustesse ────────────────────────────────────────────────────────

def test_unknown_state_falls_back_to_idle(avatar) -> None:
    """
    Un état inconnu laissait paintEvent dessiner un dégradé sans couleur :
    l'avatar disparaissait à moitié sans que rien ne l'explique.
    """
    avatar.set_state("MODE_INEXISTANT")
    assert avatar.state == IDLE
    avatar.repaint()


def test_paint_survives_a_direct_state_write(avatar) -> None:
    """Filet de sécurité : écriture directe sans passer par set_state."""
    avatar.state = "N_IMPORTE_QUOI"
    avatar.repaint()  # ne doit pas lever


# ── WATCHING : le témoin de capture ───────────────────────────────────

def test_watching_uses_a_distinct_colour() -> None:
    """
    Ambre et non cyan : le témoin doit trancher avec l'ambiance de
    l'interface, sinon il passe inaperçu.
    """
    from ui.avatar_widget import WATCHING_COLOR

    assert WATCHING_COLOR.red() > 200
    assert WATCHING_COLOR.blue() < 100, "ne doit pas se confondre avec le cyan habituel"


def test_scan_line_advances_while_watching(avatar) -> None:
    avatar.set_state(WATCHING)
    first = avatar.scan_offset
    avatar.update_animation()
    assert avatar.scan_offset != first


def test_scan_line_loops_and_stays_bounded(avatar) -> None:
    """Sans bouclage, la ligne finirait par sortir du visage."""
    avatar.set_state(WATCHING)
    for _ in range(200):
        avatar.update_animation()
        assert 0 <= avatar.scan_offset < 90


def test_gaze_is_fixed_while_watching(avatar) -> None:
    """
    Les yeux ne suivent plus la souris pendant l'analyse : Luca's regarde
    l'écran, pas le curseur.
    """
    from PySide6.QtCore import QPointF

    avatar.mouse_pos = QPointF(140, 140)
    avatar.set_state(WATCHING)
    avatar.repaint()  # le rendu doit passer par la branche à regard fixe


def test_thinking_particles_do_not_leak_into_watching(avatar) -> None:
    avatar.set_state(THINKING)
    for _ in range(30):
        avatar.update_animation()
    produced = len(avatar.particles)

    avatar.set_state(WATCHING)
    for _ in range(30):
        avatar.update_animation()

    assert produced > 0, "THINKING doit produire des particules"
    assert len(avatar.particles) <= produced, "WATCHING ne doit pas en créer"


# ── Câblage avec l'interface ──────────────────────────────────────────

def test_ui_switches_to_watching_for_a_screen_question() -> None:
    import inspect

    from ui import main_window

    source = inspect.getsource(main_window.MainWindow.send_message)
    assert 'should_use_vision' in source
    assert '"WATCHING"' in source


def test_watching_indicator_is_turned_off_after_capture() -> None:
    """
    Le témoin doit s'éteindre quand la capture s'achève, pas rester
    allumé pendant toute la génération.
    """
    import inspect

    from ui import main_window

    source = inspect.getsource(main_window.MainWindow._on_context_ready)
    assert '"THINKING"' in source


# ── Esthétique Astra ──────────────────────────────────────────────────

def test_every_state_has_a_halo_palette() -> None:
    """
    Sans arrêt de couleur, Qt dessine un halo transparent et l'avatar
    paraît amputé. Chaque mode doit avoir sa palette.
    """
    from ui.avatar_widget import HALO_PALETTES

    assert set(HALO_PALETTES) == set(PRESENCE_STATES)


def test_palettes_blend_through_at_least_three_stops() -> None:
    """
    Deux arrêts donnent un dégradé qui tranche. Astra se reconnaît à des
    teintes qui se fondent — d'où trois arrêts au minimum.
    """
    from ui.avatar_widget import HALO_PALETTES

    for state, stops in HALO_PALETTES.items():
        assert len(stops) >= 3, f"{state} : dégradé trop abrupt"
        assert stops[-1][-1] == 0, f"{state} : le halo doit s'éteindre en transparence"


def test_watching_palette_stays_amber() -> None:
    """Le témoin de capture ne doit pas se fondre dans le cyan ambiant."""
    from ui.avatar_widget import HALO_PALETTES

    for _position, red, _green, blue, _alpha in HALO_PALETTES[WATCHING]:
        assert red > blue, "la palette WATCHING doit rester chaude"


def test_breathing_never_stops(avatar) -> None:
    """
    Un avatar parfaitement immobile donne l'impression d'un programme
    planté. La respiration avance dans tous les modes.
    """
    for state in PRESENCE_STATES:
        avatar.set_state(state)
        before = avatar.breath_phase
        avatar.update_animation()
        assert avatar.breath_phase != before, f"{state} : respiration figée"


def test_body_radius_oscillates_within_bounds(avatar) -> None:
    """La respiration doit rester subtile, pas déformer le visage."""
    radii = []
    for _ in range(120):
        avatar.update_animation()
        radii.append(avatar.body_radius())

    assert max(radii) - min(radii) > 1.0, "la respiration doit être perceptible"
    assert all(42 <= r <= 48 for r in radii), "amplitude trop forte"


def test_breath_phase_stays_bounded(avatar) -> None:
    """Sans repli modulo, la phase croîtrait indéfiniment."""
    for _ in range(500):
        avatar.update_animation()
        assert 0 <= avatar.breath_phase < 2 * 3.14159265 + 0.1


# ── Animation ─────────────────────────────────────────────────────────

def test_idle_glow_breathes_within_bounds(avatar) -> None:
    avatar.set_state(IDLE)
    for _ in range(200):
        avatar.update_animation()
        assert 0.2 <= avatar.glow_intensity <= 0.9


def test_speaking_moves_the_mouth(avatar) -> None:
    avatar.set_state(SPEAKING)
    values = set()
    for _ in range(20):
        avatar.update_animation()
        values.add(round(avatar.mouth_open, 3))
    assert len(values) > 1, "la bouche doit s'animer pendant la parole"


def test_mouth_ratio_is_clamped(avatar) -> None:
    avatar.update_mouth(5.0)
    assert avatar.mouth_open == 1.0
    avatar.update_mouth(-3.0)
    assert avatar.mouth_open == 0.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
