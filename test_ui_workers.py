# test_ui_workers.py — threads de l'interface
#
# Ce qui est vérifié ici a une raison précise : depuis l'arrivée de la
# vision, construire le contexte peut prendre ~25 s (premier chargement
# de llava en VRAM). Fait dans le thread principal, ça figerait toute
# l'interface. Ces tests garantissent que ça n'arrive plus.
#
# Qt tourne en mode « offscreen » : aucune fenêtre ne s'ouvre.

from __future__ import annotations

import os
import threading

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QThread, Signal

from ui.main_window import ContextWorker


def test_context_worker_creates_its_own_core(monkeypatch) -> None:
    """
    SQLite refuse d'être utilisé depuis un autre thread que celui qui a
    ouvert la connexion. Le worker doit donc instancier son propre
    LucasCore, pas réutiliser celui de MainWindow.
    """
    created: list[str] = []

    class _FakeCore:
        def __init__(self):
            created.append("core")

        def prepare(self, text):
            return [{"role": "user", "content": text}]

        def close(self):
            created.append("closed")

    monkeypatch.setattr("ui.main_window.LucasCore", _FakeCore)

    worker = ContextWorker("bonjour")
    received: list[list] = []
    worker.ready.connect(received.append)
    worker.run()  # appel direct : pas besoin d'une boucle d'événements

    assert created == ["core", "closed"]
    assert received == [[{"role": "user", "content": "bonjour"}]]


def test_context_worker_always_closes_the_core(monkeypatch) -> None:
    """Sans fermeture, chaque message laisserait une connexion ouverte."""
    closed: list[bool] = []

    class _BrokenCore:
        def prepare(self, text):
            raise RuntimeError("Ollama injoignable")

        def close(self):
            closed.append(True)

    monkeypatch.setattr("ui.main_window.LucasCore", _BrokenCore)

    worker = ContextWorker("bonjour")
    errors: list[str] = []
    worker.error.connect(errors.append)
    worker.run()

    assert closed == [True]
    assert errors and "Préparation du contexte impossible" in errors[0]


def test_context_failure_does_not_crash_the_ui(monkeypatch) -> None:
    """
    Une erreur de contexte doit devenir un message dans le chat, pas une
    exception qui remonte dans la boucle Qt.
    """
    class _BrokenCore:
        def prepare(self, text):
            raise ConnectionError("boum")

        def close(self):
            pass

    monkeypatch.setattr("ui.main_window.LucasCore", _BrokenCore)

    worker = ContextWorker("test")
    worker.error.connect(lambda msg: None)
    worker.run()  # ne doit pas lever


def test_vision_status_message_is_used_for_screen_questions() -> None:
    """
    L'attente doit être expliquée : 25 s d'interface figée sans message
    passeraient pour un plantage.
    """
    import inspect

    from ui import main_window

    source = inspect.getsource(main_window.MainWindow.send_message)
    assert "should_use_vision" in source
    assert "regarde ton écran" in source


def test_status_variants_keep_the_base_style() -> None:
    """
    Le style passait par objectName = « status status_connecting », qui ne
    correspond à AUCUNE règle : Qt ne connaît pas les listes de classes
    CSS. Le libellé perdait fond, marges et couleur dès le premier
    message envoyé.
    """
    from PySide6.QtWidgets import QApplication

    from ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    seen: list[str] = []
    for variant in ("connecting", "thinking", "watching"):
        window._set_status("test", variant)
        label = window.status_label
        assert label.objectName() == "status", "la règle de base doit rester applicable"
        assert label.palette().color(label.backgroundRole()).name() == "#1a1a24"
        seen.append(label.palette().color(label.foregroundRole()).name())

    assert len(set(seen)) == 3, "chaque variante doit avoir sa couleur"
    window.close()
    del app


def test_avatar_speaks_only_once_the_sound_starts() -> None:
    """
    _speak() ne doit pas basculer l'avatar en SPEAKING : la synthèse
    prend plusieurs secondes, l'avatar paraîtrait parler dans le vide.
    Le basculement appartient à _on_playback_started().
    """
    import inspect

    from ui import main_window

    launch = inspect.getsource(main_window.MainWindow._speak)
    assert '"SPEAKING"' not in launch
    assert "playback_started" in launch

    on_start = inspect.getsource(main_window.MainWindow._on_playback_started)
    assert '"SPEAKING"' in on_start


def test_cancelled_context_never_emits(monkeypatch) -> None:
    """
    Une analyse VLM déjà lancée va à son terme. Mais si Cyril a appuyé
    sur Stop, sa réponse ne doit pas surgir vingt secondes plus tard dans
    une interface qu'il croyait libérée.
    """
    class _SlowCore:
        def prepare(self, text):
            return [{"role": "user", "content": text}]

        def close(self):
            pass

    monkeypatch.setattr("ui.main_window.LucasCore", _SlowCore)

    worker = ContextWorker("bonjour")
    received: list = []
    worker.ready.connect(received.append)
    worker.cancel()
    worker.run()

    assert received == [], "un contexte annulé ne doit pas remonter"


def test_cancelled_context_swallows_errors(monkeypatch) -> None:
    """Une erreur sur un travail abandonné n'a pas à polluer le chat."""
    class _BrokenCore:
        def prepare(self, text):
            raise RuntimeError("boum")

        def close(self):
            pass

    monkeypatch.setattr("ui.main_window.LucasCore", _BrokenCore)

    worker = ContextWorker("bonjour")
    errors: list = []
    worker.error.connect(errors.append)
    worker.cancel()
    worker.run()

    assert errors == []


def test_stop_handles_the_context_phase() -> None:
    """
    Le bouton Stop est visible dès l'envoi, y compris pendant les 25 s de
    chargement de llava. Il ne traitait que le worker LLM : appuyer
    pendant l'attente la plus pénible ne faisait rien.
    """
    import inspect

    from ui import main_window

    source = inspect.getsource(main_window.MainWindow.stop_generation)
    assert "context_worker" in source
    assert "cancel()" in source


def test_close_waits_for_the_context_worker() -> None:
    """
    Sans attente, Qt détruit l'objet QThread pendant que le thread tourne
    encore — « Destroyed while thread is still running ».
    """
    import inspect

    from ui import main_window

    source = inspect.getsource(main_window.MainWindow.closeEvent)
    assert "context_worker" in source
    assert "wait(" in source


def test_workers_are_initialised(app_window) -> None:
    """closeEvent lit context_worker : il doit exister dès le départ."""
    assert app_window.context_worker is None
    assert app_window.worker is None
    assert app_window.tts_worker is None


@pytest.fixture
def app_window(monkeypatch, tmp_path):
    """
    ⚠️ Bug réel trouvé le 04/08/2026 (audit "validation contre le vrai
    service" étendu à l'UI) : sans ceci, MainWindow() construit un vrai
    LucasCore() -> MemoryManager() sur le VRAI memory/lucas_memory.db de
    Cyril, et _load_history() (appelé depuis __init__) affiche donc son
    vrai historique de conversation (contenu financier compris) dans
    chat_history à chaque test — les 25+ tests déjà présents dans ce
    fichier le faisaient déjà, sans qu'aucun ne l'assertionne. Isolé sur
    une base temporaire vide, comme le reste du projet (test_router.py,
    test_finance.py...).
    """
    from PySide6.QtWidgets import QApplication

    from core.lucas_core import LucasCore
    from memory.memory_manager import MemoryManager
    from ui import main_window

    class _IsolatedLucasCore(LucasCore):
        def __init__(self):
            self.memory = MemoryManager(db_path=tmp_path / "test_memory.db")

    monkeypatch.setattr(main_window, "LucasCore", _IsolatedLucasCore)

    app = QApplication.instance() or QApplication([])
    window = main_window.MainWindow()
    yield window
    window.close()
    del app


def test_tts_worker_gets_a_thread_safe_logger() -> None:
    """
    L'UI passait self.lucas.log_event au TTSWorker. Ce worker tourne dans
    un autre thread, et SQLite refuse une connexion ouverte ailleurs :
    chaque lecture vocale levait « SQLite objects created in a thread can
    only be used in that same thread ».
    """
    import inspect

    from ui import main_window

    source = inspect.getsource(main_window.MainWindow._speak)
    # Les commentaires sont retirés : la docstring explique justement
    # pourquoi self.lucas.log_event est proscrit, et une recherche
    # textuelle brute se déclencherait dessus.
    code_only = "\n".join(
        line.split("#", 1)[0] for line in source.splitlines()
    )
    assert "self.lucas.log_event" not in code_only
    assert "save_event_from_any_thread" in code_only


def test_thread_safe_logger_works_from_a_worker(tmp_path, monkeypatch) -> None:
    """La fonction doit réellement écrire depuis un autre thread."""
    import threading

    from memory import memory_manager as mm

    monkeypatch.setattr(mm, "DB_PATH", tmp_path / "thread.db")

    results: list[bool] = []
    thread = threading.Thread(
        target=lambda: results.append(mm.save_event_from_any_thread("test", "détail"))
    )
    thread.start()
    thread.join()

    assert results == [True]


def test_thread_safe_logger_never_raises(monkeypatch) -> None:
    """Un événement perdu dégrade la trace ; une exception tue le thread."""
    from memory import memory_manager as mm

    monkeypatch.setattr(
        mm, "MemoryManager",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("base inaccessible")),
    )
    assert mm.save_event_from_any_thread("test") is False


def test_no_composite_object_name_remains() -> None:
    """Garde anti-régression sur le piège Qt."""
    import inspect

    from ui import main_window

    source = inspect.getsource(main_window)
    assert 'setObjectName("status ' not in source


def test_prepare_is_not_called_on_the_main_thread() -> None:
    """
    Garde anti-régression : send_message ne doit plus appeler prepare()
    directement, sinon le gel revient sans que rien ne le signale.
    """
    import inspect

    from ui import main_window

    source = inspect.getsource(main_window.MainWindow.send_message)
    assert "self.lucas.prepare" not in source
    assert "ContextWorker" in source


# ── STT desktop : bouton micro = fichier, PAS un vrai micro ────────────
#
# Ce PC n'a pas de microphone (VISION_LONG_TERME.md §2, Pilier 3). Les
# tests ci-dessous vérifient le câblage avec un STTEngine factice — la
# validation avec un VRAI backend Whisper sur de l'audio synthétique vit
# dans test_integration.py (marqueur "integration"), jamais ici.

class _FakeSTTResult:
    def __init__(self, text: str) -> None:
        self.text = text


def test_stt_worker_transcribes_via_the_shared_engine(monkeypatch) -> None:
    """
    Un seul STTEngine partagé (comme _stt_engine dans api/server.py) :
    recharger Whisper à chaque fichier serait coûteux.
    """
    from ui import main_window

    calls: list[str] = []

    class _FakeEngine:
        def transcribe(self, path):
            calls.append(path)
            return _FakeSTTResult("bonjour Luca's")

    monkeypatch.setattr(main_window, "_stt_engine", _FakeEngine())

    worker = main_window.STTWorker("extrait.wav")
    received: list[str] = []
    worker.transcribed.connect(received.append)
    worker.run()  # appel direct : pas besoin d'une boucle d'événements

    assert calls == ["extrait.wav"]
    assert received == ["bonjour Luca's"]


def test_stt_worker_reports_unavailable_as_a_readable_error(monkeypatch) -> None:
    from modules.stt_engine import STTUnavailable
    from ui import main_window

    class _FakeEngine:
        def transcribe(self, path):
            raise STTUnavailable("aucun backend Whisper installé")

    monkeypatch.setattr(main_window, "_stt_engine", _FakeEngine())

    worker = main_window.STTWorker("extrait.wav")
    errors: list[str] = []
    worker.error.connect(errors.append)
    worker.run()

    assert errors and "Transcription impossible" in errors[0]


def test_stt_worker_never_crashes_on_an_unexpected_error(monkeypatch) -> None:
    """Comme ContextWorker : une erreur de transcription ne doit jamais faire tomber le thread."""
    from ui import main_window

    class _BrokenEngine:
        def transcribe(self, path):
            raise RuntimeError("fichier audio corrompu")

    monkeypatch.setattr(main_window, "_stt_engine", _BrokenEngine())

    worker = main_window.STTWorker("extrait.wav")
    worker.error.connect(lambda msg: None)
    worker.run()  # ne doit pas lever


def test_transcribe_audio_file_does_nothing_when_the_dialog_is_cancelled(app_window, monkeypatch) -> None:
    """Annuler la sélection de fichier ne doit lancer aucune transcription."""
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))

    app_window.transcribe_audio_file()

    assert app_window.stt_worker is None


def test_on_transcribed_fills_the_input_field_without_sending(app_window) -> None:
    """
    Cyril garde la main : le texte transcrit remplit le champ de saisie,
    il n'est jamais envoyé automatiquement.
    """
    app_window._on_transcribed("quel temps fait-il")

    assert app_window.input_field.text() == "quel temps fait-il"
    assert app_window.worker is None, "aucune génération ne doit démarrer toute seule"


def test_on_stt_error_appends_a_message_to_the_chat(app_window) -> None:
    app_window._on_stt_error("aucun backend Whisper installé")

    assert "[STT]" in app_window.chat_history.toPlainText()
    assert "aucun backend Whisper installé" in app_window.chat_history.toPlainText()


def test_mic_button_is_wired_to_transcribe_audio_file() -> None:
    import inspect

    from ui import main_window

    source = inspect.getsource(main_window.MainWindow.__init__)
    assert "self.mic_button.clicked.connect(self.transcribe_audio_file)" in source


def test_close_waits_for_the_stt_worker() -> None:
    import inspect

    from ui import main_window

    source = inspect.getsource(main_window.MainWindow.closeEvent)
    assert "stt_worker" in source
    assert "wait(" in source


def test_stt_worker_is_initialised(app_window) -> None:
    """closeEvent lit stt_worker : il doit exister dès le départ."""
    assert app_window.stt_worker is None


# ── TTSWorker ─────────────────────────────────────────────────────────
#
# Jamais testé directement avant l'audit "validation contre le vrai
# service" du 04/08/2026 : seule sa présence dans un commentaire
# apparaissait dans ce fichier, `run()` n'était exercé par aucun test.


class _FakeVoiceManager:
    def __init__(self, spoken="data/output.mp3", log_event=None):
        self._spoken = spoken
        self.log_event = log_event

    def speak(self, text, question="", on_playback_start=None):
        if on_playback_start is not None:
            on_playback_start()
        return self._spoken


def test_tts_worker_speaks_and_signals_playback_start(monkeypatch) -> None:
    from ui import main_window

    monkeypatch.setattr(main_window, "HAS_VOICE", True)
    monkeypatch.setattr(main_window, "VoiceManager", _FakeVoiceManager)

    worker = main_window.TTSWorker("Bonjour Cyril", "quelle heure est-il ?")
    started: list[bool] = []
    finished: list[bool] = []
    worker.playback_started.connect(lambda: started.append(True))
    worker.finished.connect(lambda: finished.append(True))
    worker.run()  # appel direct : même patron que STTWorker ci-dessus

    assert started == [True]
    assert finished == [True]


def test_tts_worker_reports_sensitive_content_skipped(monkeypatch) -> None:
    from ui import main_window

    monkeypatch.setattr(main_window, "HAS_VOICE", True)
    monkeypatch.setattr(
        main_window, "VoiceManager", lambda log_event=None: _FakeVoiceManager(spoken=None)
    )

    worker = main_window.TTSWorker("mon salaire net", "quel est mon salaire ?")
    errors: list[str] = []
    worker.error.connect(errors.append)
    worker.run()

    assert errors == [main_window.SENSITIVE_SKIPPED_MESSAGE]


def test_tts_worker_reports_missing_voice_module(monkeypatch) -> None:
    from ui import main_window

    monkeypatch.setattr(main_window, "HAS_VOICE", False)

    worker = main_window.TTSWorker("Bonjour")
    errors: list[str] = []
    worker.error.connect(errors.append)
    worker.run()

    assert errors == ["Module voix non disponible"]


def test_tts_worker_never_crashes_on_an_unexpected_error(monkeypatch) -> None:
    """Comme STTWorker/ContextWorker : une panne de synthèse ne doit jamais faire tomber le thread."""
    from ui import main_window

    class _BrokenVoiceManager:
        def __init__(self, log_event=None):
            pass

        def speak(self, text, question="", on_playback_start=None):
            raise RuntimeError("edge_tts injoignable")

    monkeypatch.setattr(main_window, "HAS_VOICE", True)
    monkeypatch.setattr(main_window, "VoiceManager", _BrokenVoiceManager)

    worker = main_window.TTSWorker("Bonjour")
    errors: list[str] = []
    finished: list[bool] = []
    worker.error.connect(errors.append)
    worker.finished.connect(lambda: finished.append(True))
    worker.run()  # ne doit pas lever

    assert errors == ["edge_tts injoignable"]
    assert finished == [True]


# ── send_message() : le flux principal du chat ──────────────────────
#
# Jamais exercé avant l'audit du 04/08/2026 : c'est pourtant le chemin le
# plus emprunté de toute l'UI (chaque message tapé par Cyril). Les fakes
# remplacent ContextWorker/LLMWorker par un `start()` synchrone — même
# principe que STTWorker/TTSWorker plus haut (appel direct, pas de vraie
# boucle de threads Qt à orchestrer).


def test_send_message_runs_the_full_pipeline_to_a_complete_response(app_window, monkeypatch) -> None:
    from PySide6.QtCore import QThread, Signal

    from ui import main_window

    class _FakeContext(QThread):
        ready = Signal(list)
        error = Signal(str)

        def __init__(self, question, log_event=None):
            super().__init__()
            self.question = question

        def start(self):
            self.ready.emit([{"role": "user", "content": self.question}])

    class _FakeLLM(QThread):
        token_received = Signal(str)
        response_complete = Signal(str)
        error_occurred = Signal(str)
        started_thinking = Signal()

        def __init__(self, messages):
            super().__init__()
            self.messages = messages

        def start(self):
            # ⚠️ Le texte affiché vient EXCLUSIVEMENT du cumul des jetons
            # streamés (_on_token) ; response_complete() ne fait que
            # sauvegarder full_answer et déclencher le TTS, jamais un
            # second affichage. Les deux doivent donc être cohérents ici,
            # comme en production (les jetons réels s'additionnent en
            # full_answer réel).
            self.started_thinking.emit()
            self.token_received.emit("Bonjour")
            self.token_received.emit(" Cyril")
            self.response_complete.emit("Bonjour Cyril")

    monkeypatch.setattr(main_window, "ContextWorker", _FakeContext)
    monkeypatch.setattr(main_window, "LLMWorker", _FakeLLM)
    monkeypatch.setattr(main_window, "should_use_vision", lambda *a, **k: False)

    app_window.input_field.setText("bonjour Luca's")
    app_window.send_message()

    history = app_window.chat_history.toPlainText()
    assert "bonjour Luca's" in history
    assert "Bonjour Cyril" in history
    assert app_window.input_field.text() == ""
    assert app_window.last_user_message == "bonjour Luca's"
    assert app_window.last_lucas_response == "Bonjour Cyril"


def test_send_message_ignores_an_empty_input(app_window) -> None:
    app_window.input_field.setText("   ")
    app_window.send_message()

    assert app_window.context_worker is None
    assert app_window.chat_history.toPlainText() == ""


def test_send_message_switches_the_avatar_to_watching_for_screen_questions(app_window, monkeypatch) -> None:
    from PySide6.QtCore import QThread, Signal

    from ui import main_window

    class _FakeContext(QThread):
        ready = Signal(list)
        error = Signal(str)

        def __init__(self, question, log_event=None):
            super().__init__()

        def start(self):
            pass  # la réponse n'arrive jamais : seul l'état initial nous intéresse ici

    monkeypatch.setattr(main_window, "ContextWorker", _FakeContext)
    monkeypatch.setattr(main_window, "should_use_vision", lambda *a, **k: True)

    app_window.input_field.setText("décris mon écran")
    app_window.send_message()

    assert app_window.avatar.state == "WATCHING" if main_window.HAS_AVATAR else True


# ── stop_generation() / closeEvent() ─────────────────────────────────
#
# Dernier trou signalé comme "rendements décroissants" dans le rapport du
# 04/08/2026 : isRunning() a besoin d'un VRAI thread démarré, pas d'un
# run() appelé directement comme STTWorker/TTSWorker plus haut. Ces
# workers de test bloquent réellement (threading.Event) le temps du
# test — thread réel, pas de code de production (LucasCore/Ollama)
# exécuté dedans.


def _wait_until_running(worker, timeout=2.0) -> None:
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if worker.isRunning():
            return
        time.sleep(0.005)
    raise AssertionError("le thread de test n'a jamais démarré à temps")


class _BlockingContextWorker(QThread):
    """Vrai QThread, run() bloquant jusqu'à cancel() — pas de code de production dedans."""

    ready = Signal(list)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self.cancelled = False
        self._release = threading.Event()

    def cancel(self):
        self.cancelled = True
        self._release.set()

    def run(self):
        self._release.wait(3)  # filet de sécurité si cancel() n'arrive jamais


class _BlockingLLMWorker(QThread):
    """Vrai QThread, run() bloquant jusqu'à stop() — pas de code de production dedans."""

    token_received = Signal(str)
    response_complete = Signal(str)
    error_occurred = Signal(str)
    started_thinking = Signal()

    def __init__(self):
        super().__init__()
        self.stopped = False
        self._release = threading.Event()

    def stop(self):
        self.stopped = True
        self._release.set()
        self.wait(1000)

    def run(self):
        self._release.wait(3)


def test_stop_generation_interrupts_a_running_context_worker(app_window) -> None:
    worker = _BlockingContextWorker()
    app_window.context_worker = worker
    worker.start()
    _wait_until_running(worker)

    app_window.stop_generation()

    assert worker.cancelled is True
    assert "[Génération interrompue]" in app_window.chat_history.toPlainText()
    # isVisible() exigerait un show() du widget parent (même famille que le
    # bug repaint()/offscreen déjà trouvé) — isEnabled() n'en dépend pas.
    assert app_window.input_field.isEnabled() is True
    worker.wait(2000)


def test_stop_generation_interrupts_a_running_llm_worker(app_window) -> None:
    worker = _BlockingLLMWorker()
    app_window.worker = worker
    worker.start()
    _wait_until_running(worker)

    app_window.stop_generation()

    assert worker.stopped is True
    assert "[Génération interrompue]" in app_window.chat_history.toPlainText()


def test_stop_generation_does_nothing_when_nothing_is_running(app_window) -> None:
    """Ni context_worker ni worker : Stop ne doit rien afficher."""
    app_window.stop_generation()
    assert app_window.chat_history.toPlainText() == ""


def test_close_event_waits_for_a_running_context_worker(app_window) -> None:
    from PySide6.QtGui import QCloseEvent

    worker = _BlockingContextWorker()
    app_window.context_worker = worker
    worker.start()
    _wait_until_running(worker)

    app_window.closeEvent(QCloseEvent())  # ne doit pas lever, ni planter sur un thread encore actif

    assert worker.cancelled is True
    assert worker.isRunning() is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
