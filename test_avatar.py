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


def test_listening_is_triggered_by_typing() -> None:
    """
    LISTENING ne veut pas dire « micro ouvert » mais « Cyril s'adresse à
    Luca's ». Il est déclenché par la saisie clavier, donc les cinq modes
    sont atteignables dès aujourd'hui — contrairement à ce que laissait
    croire une première rédaction de ce module.
    """
    import inspect

    from ui import main_window

    source = inspect.getsource(main_window.MainWindow._on_typing)
    assert '"LISTENING"' in source


def test_clearing_the_input_returns_to_idle(app) -> None:
    """
    Effacer sa saisie laissait l'avatar en LISTENING indéfiniment, y
    compris après avoir renoncé à écrire.
    """
    from ui.main_window import MainWindow

    window = MainWindow()
    window.input_field.setText("bonjour")
    assert window.avatar.state == "LISTENING"

    window.input_field.setText("")
    assert window.avatar.state == IDLE
    window.close()


def test_typing_does_not_disturb_a_running_generation(app, monkeypatch) -> None:
    """
    Effacer son texte pendant que Luca's réfléchit la ferait paraître au
    repos alors qu'elle travaille.
    """
    from ui.main_window import MainWindow

    window = MainWindow()
    window._set_avatar_state(THINKING)

    class _Busy:
        @staticmethod
        def isRunning():
            return True

        @staticmethod
        def stop():
            """closeEvent() interrompt le worker en cours."""

    window.worker = _Busy()
    window.input_field.setText("texte")
    assert window.avatar.state == THINKING

    window.input_field.setText("")
    assert window.avatar.state == THINKING
    window.close()


def test_every_state_has_a_status_label() -> None:
    """
    WATCHING manquait : le libellé disait « En ligne » pendant que
    l'avatar virait à l'ambre. Deux indicateurs qui se contredisent sont
    pires qu'un seul.
    """
    import inspect

    from ui import main_window

    source = inspect.getsource(main_window.MainWindow._set_avatar_state)
    for state in PRESENCE_STATES:
        assert f'"{state}"' in source, f"{state} n'a pas de libellé de statut"


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
    assert "should_use_vision" in source
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


def test_scan_line_follows_the_breathing_radius() -> None:
    """
    La ligne de balayage suivait un rayon de 45 en dur. Depuis que le
    visage respire, ça la faisait déborder ou rentrer au rythme de la
    respiration.
    """
    import inspect

    from ui import avatar_widget

    source = inspect.getsource(avatar_widget.AvatarWidget.paintEvent)
    assert "45.0**2" not in source
    assert "radius**2" in source


def test_no_state_string_literals_remain() -> None:
    """
    Les états sont des constantes : un littéral résiduel échapperait à
    tout renommage et à la vérification de set_state().
    """
    import inspect

    from ui import avatar_widget

    source = inspect.getsource(avatar_widget)
    assert 'self.state == "' not in source


def test_breath_phase_stays_bounded(avatar) -> None:
    """Sans repli modulo, la phase croîtrait indéfiniment."""
    for _ in range(500):
        avatar.update_animation()
        assert 0 <= avatar.breath_phase < 2 * 3.14159265 + 0.1


# ── Fondu entre modes ─────────────────────────────────────────────────


def test_changing_state_starts_a_transition(avatar) -> None:
    """
    Un basculement instantané de couleur donne l'impression d'un défaut
    d'affichage plutôt que d'un changement d'état.
    """
    avatar.set_state(IDLE)
    avatar.transition = 1.0
    avatar.set_state(WATCHING)

    assert avatar.transition == 0.0
    assert avatar.previous_state == IDLE


def test_setting_the_same_state_does_not_restart_a_transition(avatar) -> None:
    """Sinon un rafraîchissement répété figerait l'avatar en plein fondu."""
    avatar.set_state(THINKING)
    for _ in range(20):
        avatar.update_animation()
    assert avatar.transition == 1.0

    avatar.set_state(THINKING)
    assert avatar.transition == 1.0


def test_transition_completes_and_stops(avatar) -> None:
    from ui.avatar_widget import TRANSITION_FRAMES

    avatar.set_state(WATCHING)
    for _ in range(TRANSITION_FRAMES + 2):
        avatar.update_animation()

    assert avatar.transition == 1.0, "le fondu doit se terminer"


def test_palette_is_between_the_two_states_mid_transition(avatar) -> None:
    """Au milieu du fondu, la couleur ne doit être ni l'une ni l'autre."""
    from ui.avatar_widget import HALO_PALETTES

    avatar.set_state(IDLE)
    avatar.transition = 1.0
    avatar.set_state(WATCHING)
    avatar.transition = 0.5

    blended = avatar.current_palette()
    assert blended != HALO_PALETTES[IDLE]
    assert blended != HALO_PALETTES[WATCHING]
    # Le rouge doit avoir progressé de l'IDLE (0) vers le WATCHING (255).
    assert 0 < blended[0][1] < 255


def test_border_follows_the_same_fade(avatar) -> None:
    """
    Sans ça le contour claquerait tout seul pendant que le halo se fond
    doucement — plus voyant qu'une transition franche.
    """
    avatar.set_state(IDLE)
    avatar.transition = 1.0
    cyan = avatar.border_color()

    avatar.set_state(WATCHING)
    avatar.transition = 0.5
    middle = avatar.border_color()

    avatar.transition = 1.0
    amber = avatar.border_color()

    assert cyan.red() < middle.red() < amber.red()


def test_easing_is_smooth_at_both_ends(avatar) -> None:
    """
    Une interpolation linéaire démarre et s'arrête net ; l'œil le perçoit
    comme une saccade même sur 400 ms.
    """
    ease = avatar._ease
    assert ease(0.0) == 0.0
    assert ease(1.0) == 1.0
    assert ease(0.5) == pytest.approx(0.5)
    # Départ plus lent que le milieu : c'est ce qui adoucit l'amorce.
    assert ease(0.1) < 0.1


def test_every_state_renders_mid_transition(avatar) -> None:
    """Le rendu doit tenir à n'importe quel instant du fondu."""
    for state in PRESENCE_STATES:
        avatar.set_state(state)
        for progress in (0.0, 0.25, 0.5, 0.75, 1.0):
            avatar.transition = progress
            avatar.repaint()


# ── Libellé ───────────────────────────────────────────────────────────


def test_every_state_has_a_readable_label() -> None:
    """« WATCHING » sous le visage ne dit rien à Cyril."""
    from ui.avatar_widget import STATE_LABELS

    assert set(STATE_LABELS) == set(PRESENCE_STATES)
    for label in STATE_LABELS.values():
        assert label.islower(), "un libellé, pas une constante"
        assert label.isalpha() or " " in label


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
