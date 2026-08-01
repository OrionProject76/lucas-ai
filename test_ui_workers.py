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
    OrionCore, pas réutiliser celui de MainWindow.
    """
    created: list[str] = []

    class _FakeCore:
        def __init__(self):
            created.append("core")

        def prepare(self, text):
            return [{"role": "user", "content": text}]

        def close(self):
            created.append("closed")

    monkeypatch.setattr("ui.main_window.OrionCore", _FakeCore)

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

    monkeypatch.setattr("ui.main_window.OrionCore", _BrokenCore)

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

    monkeypatch.setattr("ui.main_window.OrionCore", _BrokenCore)

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
    assert "self.orion.prepare" not in source
    assert "ContextWorker" in source


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
