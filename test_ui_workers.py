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

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

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
def app_window():
    from PySide6.QtWidgets import QApplication

    from ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
