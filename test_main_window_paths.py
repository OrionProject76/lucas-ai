# test_main_window_paths.py — les chemins de MainWindow que rien ne couvrait
#
# ⚠️ Pourquoi ce fichier existe (06/08/2026)
# ------------------------------------------
# En ouvrant le chantier `ui/`, deux choses sont apparues :
#
#   1. `ui/` n'était PAS mesuré par `just test` — sa couverture n'existait
#      simplement pas, personne ne pouvait donc savoir ce qui manquait.
#   2. `ui/avatar_widget.py` affichait 87 %, et les 30 lignes « manquantes »
#      étaient son bloc `if __name__ == "__main__":` — une démo qu'aucun
#      test ne doit exécuter. Une fois exclue (voir .coveragerc), ce
#      fichier est à 100 % : le trou n'existait pas.
#
# Restait `ui/main_window.py`, à 87 % avec de vrais manques. Ce fichier
# couvre ceux qui comptent — les chemins d'ERREUR et de VOIX, ceux qui
# décident de ce que Cyril voit quand quelque chose se passe mal.
#
# Qt tourne en mode « offscreen » : aucune fenêtre ne s'ouvre.

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from ui.avatar_widget import IDLE, SPEAKING


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from ui.main_window import MainWindow

    fenetre = MainWindow()
    yield fenetre
    fenetre.close()


# ── Chemin d'erreur du LLM ────────────────────────────────────────────

def test_an_llm_error_is_shown_to_cyril_not_swallowed(window) -> None:
    """
    Une panne de génération doit APPARAÎTRE dans la conversation.

    Muette, elle laisserait Luca's figée sur « réfléchit… » sans que rien
    n'explique pourquoi — le motif d'échec silencieux traqué dans tout ce
    projet, transposé à l'interface.
    """
    window._on_error("Ollama injoignable")

    assert "Ollama injoignable" in window.chat_history.toPlainText()
    assert window.avatar is not None
    assert window.avatar.state == IDLE, "l'avatar doit revenir au repos, pas rester figé"


def test_an_llm_error_gives_the_input_back(window) -> None:
    """Après une erreur, Cyril doit pouvoir réessayer immédiatement."""
    window.input_field.setEnabled(False)
    window._on_error("panne")
    assert window.input_field.isEnabled(), "la saisie doit être rendue après une erreur"


# ── Chemin de la voix ─────────────────────────────────────────────────

def test_a_tts_failure_is_written_in_the_conversation(window) -> None:
    """
    ⚠️ Le cas qui compte le plus de ce fichier.

    Quand Piper est indisponible sur du contenu sensible, RIEN n'est
    prononcé — c'est la règle (CLAUDE.md, routage TTS). Mais un silence
    non expliqué est indiscernable d'une panne : Cyril croirait la voix
    cassée alors que Luca's protège ses données.

    Le message doit donc atterrir dans la conversation, visible.
    """
    from modules.voice_manager import SENSITIVE_SKIPPED_MESSAGE

    window._on_tts_error(SENSITIVE_SKIPPED_MESSAGE)

    assert SENSITIVE_SKIPPED_MESSAGE in window.chat_history.toPlainText()
    assert window.avatar is not None
    assert window.avatar.state == IDLE


def test_the_avatar_speaks_only_once_the_sound_starts(window) -> None:
    """
    SPEAKING au lancement de la synthèse mentirait : la synthèse prend
    un temps variable, et l'avatar « parlerait » dans le silence.
    Le passage se fait sur `playback_started`, pas avant.
    """
    assert window.avatar is not None
    window._on_playback_started()
    assert window.avatar.state == SPEAKING
    assert not window.status_label.isVisible(), "le statut cède la place à la parole"


def test_the_avatar_returns_to_rest_when_the_voice_ends(window) -> None:
    window._on_tts_finished()
    assert window.avatar is not None
    assert window.avatar.state == IDLE


# ── Bascule TTS ───────────────────────────────────────────────────────

def test_toggling_tts_off_changes_the_state_and_the_button(window) -> None:
    """L'état ET l'affichage doivent suivre : un bouton qui ment sur
    l'état réel de la voix est pire que pas de bouton."""
    window.toggle_tts(False)
    assert window.tts_auto is False
    infobulle_off = window.tts_button.toolTip()

    window.toggle_tts(True)
    assert window.tts_auto is True
    assert window.tts_button.toolTip() != infobulle_off


# ── Premier jeton ─────────────────────────────────────────────────────

def test_the_first_token_hides_the_waiting_status(window) -> None:
    """
    « Réflexion… » doit disparaître dès que la réponse commence, sinon
    les deux se superposent et Cyril ne sait plus laquelle lire.
    """
    window.status_label.setVisible(True)
    window._on_token("Salut")
    assert not window.status_label.isVisible()
