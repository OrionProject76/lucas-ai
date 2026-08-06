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
    # ⚠️ `show()` + un tour de boucle, sinon `isVisible()` MENT.
    #
    # Trouvé le 06/08/2026, et c'est le jumeau exact du piège déjà
    # documenté pour `repaint()` dans test_avatar.py (ROADMAP.md §5.17) :
    # sous QT_QPA_PLATFORM=offscreen, `setVisible(True)` sur un widget
    # dont la fenêtre n'a jamais été montrée laisse `isVisible()` à False.
    #
    # Sans ces deux lignes, le test du premier jeton passait SANS RIEN
    # VÉRIFIER : la branche `if self.status_label.isVisible():` n'était
    # jamais prise, et l'assertion « le statut est masqué » était vraie
    # d'avance. La couverture l'a révélé — la ligne restait rouge malgré
    # un test vert qui prétendait la couvrir.
    fenetre.show()
    app.processEvents()
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


# ── Replis gracieux quand un module optionnel manque ───────────────────
#
# ⚠️ Ces deux tests RECHARGENT `ui.main_window` avec un import neutralisé,
# puis le rechargent une seconde fois pour rendre le module intact. Sans
# cette restauration, tous les tests suivants verraient un module où
# l'avatar ou la voix n'existe plus.

def _recharge_sans(nom_module: str, *attributs: str) -> dict:
    """Recharge ui.main_window sans `nom_module`, et rend ses attributs.

    `sys.modules[nom] = None` fait lever ImportError à l'import — c'est
    le mécanisme documenté de CPython, pas une astuce.

    ⚠️ Rend un DICTIONNAIRE, pas le module, et c'est délibéré :
    `importlib.reload()` mute l'objet module EN PLACE. Rendre le module
    laisserait l'appelant lire des attributs déjà réécrits par la
    restauration — première version de ce helper, qui affirmait
    `HAS_VOICE is False` sur un module redevenu normal entre-temps. Les
    valeurs sont donc capturées AVANT de restaurer.
    """
    import importlib
    import sys

    import ui.main_window as mw

    ancien = sys.modules.get(nom_module)
    sys.modules[nom_module] = None  # type: ignore[assignment]  # ImportError a l'import
    try:
        recharge = importlib.reload(mw)
        return {nom: getattr(recharge, nom, None) for nom in attributs}
    finally:
        if ancien is None:
            sys.modules.pop(nom_module, None)
        else:
            sys.modules[nom_module] = ancien
        importlib.reload(mw)  # remet le module intact pour la suite


def test_a_missing_avatar_module_does_not_break_the_window(app) -> None:
    """
    L'avatar est optionnel. Son absence doit dégrader l'interface, pas
    l'empêcher de démarrer — sinon une dépendance graphique cassée rendrait
    Luca's entièrement inutilisable.
    """
    valeurs = _recharge_sans("ui.avatar_widget", "HAS_AVATAR")
    assert valeurs["HAS_AVATAR"] is False


def test_a_missing_voice_module_leaves_a_readable_message(app) -> None:
    """
    Sans VoiceManager, le repli doit quand même fournir le message de
    contenu sensible non prononcé : c'est lui qui distingue « Luca's
    protège tes données » de « la voix est cassée ».
    """
    valeurs = _recharge_sans(
        "modules.voice_manager", "HAS_VOICE", "SENSITIVE_SKIPPED_MESSAGE"
    )
    assert valeurs["HAS_VOICE"] is False
    assert "sensible" in valeurs["SENSITIVE_SKIPPED_MESSAGE"].lower()


# ── Fenêtre construite sans avatar ────────────────────────────────────

def test_the_window_builds_without_an_avatar(app, monkeypatch) -> None:
    """Le placeholder remplace l'avatar, la fenêtre reste utilisable."""
    from ui import main_window as mw

    monkeypatch.setattr(mw, "HAS_AVATAR", False)
    fenetre = mw.MainWindow()
    try:
        assert fenetre.avatar is None
        assert fenetre.input_field.isEnabled(), "la saisie doit rester utilisable"
    finally:
        fenetre.close()


def test_typing_without_an_avatar_does_not_crash(window) -> None:
    """`_on_typing` doit sortir proprement quand il n'y a pas d'avatar."""
    window.avatar = None
    window.input_field.setText("bonjour")  # déclenche _on_typing
    assert window.avatar is None


# ── Chaîne TTS complète ───────────────────────────────────────────────

class _FauxTTSWorker:
    """Double de TTSWorker : ne démarre AUCUN thread réel.

    Les tests ne doivent pas lancer de vrais QThread — ils survivraient
    au test, joueraient du son, et rendraient la suite dépendante d'une
    carte audio.
    """

    def __init__(self, text, question, log_event):
        self.text = text
        self.demarre = False

    class _Signal:
        def connect(self, _):
            pass

    playback_started = _Signal()
    finished = _Signal()
    error = _Signal()

    def start(self):
        self.demarre = True

    def isRunning(self):
        return True

    def wait(self, ms):
        return True


def test_an_answer_is_spoken_when_tts_auto_is_on(window, monkeypatch) -> None:
    """`_on_complete` doit passer la main à la voix, pas retomber en IDLE."""
    from ui import main_window as mw

    parle: list[str] = []
    monkeypatch.setattr(mw, "HAS_VOICE", True)
    monkeypatch.setattr(window, "_speak", lambda texte: parle.append(texte))
    window.tts_auto = True

    window._on_complete("voici ma réponse")
    assert parle == ["voici ma réponse"]


def test_an_empty_answer_is_never_spoken(window, monkeypatch) -> None:
    """Synthétiser du vide ferait patienter Cyril devant un silence."""
    from ui import main_window as mw

    parle: list[str] = []
    monkeypatch.setattr(mw, "HAS_VOICE", True)
    monkeypatch.setattr(window, "_speak", lambda texte: parle.append(texte))
    window.tts_auto = True

    window._on_complete("   ")
    assert parle == []
    assert window.avatar is not None
    assert window.avatar.state == IDLE


def test_speaking_starts_a_worker_and_announces_the_synthesis(window, monkeypatch) -> None:
    from ui import main_window as mw

    monkeypatch.setattr(mw, "TTSWorker", _FauxTTSWorker)
    window._speak("bonjour Cyril")

    assert isinstance(window.tts_worker, _FauxTTSWorker)
    assert window.tts_worker.demarre, "le worker doit être démarré"
    assert window.tts_worker.text == "bonjour Cyril"


# ── Transcription d'un fichier audio ──────────────────────────────────

class _FauxSTTWorker:
    def __init__(self, path):
        self.path = path
        self.demarre = False

    class _Signal:
        def connect(self, _):
            pass

    transcribed = _Signal()
    error = _Signal()

    def start(self):
        self.demarre = True

    def isRunning(self):
        return True

    def wait(self, ms):
        return True


def test_choosing_no_file_does_nothing(window, monkeypatch) -> None:
    """Annuler la boîte de dialogue ne doit rien déclencher."""
    from ui import main_window as mw

    monkeypatch.setattr(mw.QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    window.transcribe_audio_file()
    assert window.stt_worker is None or not getattr(window.stt_worker, "demarre", False)


def test_choosing_a_file_starts_the_transcription(window, monkeypatch) -> None:
    from ui import main_window as mw

    monkeypatch.setattr(
        mw.QFileDialog, "getOpenFileName", lambda *a, **k: ("C:/audio/test.wav", "")
    )
    monkeypatch.setattr(mw, "STTWorker", _FauxSTTWorker)

    window.transcribe_audio_file()

    assert isinstance(window.stt_worker, _FauxSTTWorker)
    assert window.stt_worker.demarre
    assert window.stt_worker.path == "C:/audio/test.wav"
    assert not window.mic_button.isEnabled(), "le bouton se verrouille pendant la transcription"


# ── Fermeture ─────────────────────────────────────────────────────────

def test_closing_waits_for_the_running_workers(window, monkeypatch) -> None:
    """
    Fermer sans attendre laisserait des QThread écrire dans une base
    déjà fermée — plantage à la sortie, sans rapport visible avec la
    cause.
    """
    attentes: list[str] = []

    class _Occupe:
        def __init__(self, nom):
            self.nom = nom

        def isRunning(self):
            return True

        def wait(self, ms):
            attentes.append(self.nom)
            return True

        def stop(self):
            attentes.append(f"{self.nom}:stop")

    window.worker = _Occupe("llm")
    window.tts_worker = _Occupe("tts")
    window.stt_worker = _Occupe("stt")

    from PySide6.QtGui import QCloseEvent

    window.closeEvent(QCloseEvent())

    assert "tts" in attentes, "le worker TTS doit être attendu"
    assert "stt" in attentes, "le worker STT doit être attendu"
