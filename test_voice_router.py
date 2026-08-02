# test_voice_router.py — routage TTS local/cloud et garde sur le sensible
#
# Règle testée : un contenu sensible n'est jamais prononcé par edge_tts
# (donc jamais envoyé à Microsoft), sauf interrupteur explicite dans
# config.py. Voir CLAUDE.md règle 3, section TTS.
#
# Aucun appel réseau, aucun son joué : Piper et edge_tts sont mockés.

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.router import route_voice
from modules import voice_manager as vm_module
from modules.piper_engine import PiperEngine, PiperUnavailable
from modules.voice_manager import VoiceManager

# ── route_voice() ─────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "question, answer, expected, why",
    [
        ("quel temps fait-il ?", "Il fait beau à Paris.", "cloud", "rien de sensible"),
        ("quel est mon salaire ?", "Il est de 3200 euros.", "local", "question sensible seule"),
        ("comment ça va ?", "Ton portfolio a progressé.", "local", "réponse sensible seule"),
        ("résume le document", "Voici le résumé.", "local", "question RAG"),
        ("raconte une blague", "Toc toc.", "cloud", "défaut cloud"),
        ("", "Mes dépenses du mois sont élevées.", "local", "sensible sans question"),
    ],
)
def test_route_voice(question: str, answer: str, expected: str, why: str) -> None:
    assert route_voice(answer, question) == expected, f"{why}"


def test_question_alone_is_enough_to_force_local() -> None:
    """Le cas central : la réponse seule paraît anodine."""
    answer = "Il est de 3200 euros."
    assert route_voice(answer) == "cloud"          # réponse seule : rien à signaler
    assert route_voice(answer, "quel est mon salaire ?") == "local"


# ── VoiceManager : ce qui part réellement ─────────────────────────────

class _Spy:
    """Enregistre les appels aux moteurs et au logger."""

    def __init__(self) -> None:
        self.edge_calls: list[str] = []
        self.piper_calls: list[str] = []
        self.events: list[tuple[str, str]] = []

    def log_event(self, event_type: str, details: str = "") -> None:
        self.events.append((event_type, details))


@pytest.fixture
def spy_manager(monkeypatch) -> tuple[VoiceManager, _Spy]:
    """VoiceManager dont les deux moteurs sont mockés."""
    spy = _Spy()
    manager = VoiceManager(log_event=spy.log_event)

    def fake_edge(text: str, output_path: str | None = None) -> str:
        spy.edge_calls.append(text)
        return "data/output.mp3"

    def fake_piper(text: str, output_path: str | None = None) -> str:
        spy.piper_calls.append(text)
        return "data/output_piper.wav"

    monkeypatch.setattr(manager, "_synthesize_edge", fake_edge)
    monkeypatch.setattr(manager, "_synthesize_piper", fake_piper)
    return manager, spy


def test_neutral_content_goes_to_edge(spy_manager) -> None:
    manager, spy = spy_manager
    manager._synthesize_routed("Il fait beau.", "quel temps fait-il ?")
    assert spy.edge_calls == ["Il fait beau."]
    assert spy.piper_calls == []
    assert spy.events == []


def test_sensitive_content_goes_to_piper(spy_manager) -> None:
    manager, spy = spy_manager
    manager._synthesize_routed("Il est de 3200 euros.", "quel est mon salaire ?")
    assert spy.piper_calls == ["Il est de 3200 euros."]
    assert spy.edge_calls == [], "un contenu sensible ne doit jamais partir chez Microsoft"


def test_piper_unavailable_stays_silent_by_default(spy_manager, monkeypatch) -> None:
    """Défaut : pas de son plutôt qu'une fuite vers le cloud."""
    manager, spy = spy_manager
    monkeypatch.setattr(vm_module, "TTS_ALLOW_CLOUD_ON_SENSITIVE", False)
    monkeypatch.setattr(
        manager, "_synthesize_piper",
        lambda text, output_path=None: (_ for _ in ()).throw(PiperUnavailable("modèle absent")),
    )

    result = manager._synthesize_routed("Mon portfolio vaut 50000 euros.", "")

    assert result is None, "rien ne doit être prononcé"
    assert spy.edge_calls == [], "aucun repli cloud sur du sensible"
    assert [e[0] for e in spy.events] == ["tts_skipped_sensitive"]


def test_piper_unavailable_uses_edge_when_flag_is_on(spy_manager, monkeypatch) -> None:
    """Cyril a levé la garde explicitement dans config.py."""
    manager, spy = spy_manager
    monkeypatch.setattr(vm_module, "TTS_ALLOW_CLOUD_ON_SENSITIVE", True)
    monkeypatch.setattr(
        manager, "_synthesize_piper",
        lambda text, output_path=None: (_ for _ in ()).throw(PiperUnavailable("modèle absent")),
    )

    result = manager._synthesize_routed("Mon portfolio vaut 50000 euros.", "")

    assert result == "data/output.mp3"
    assert spy.edge_calls == ["Mon portfolio vaut 50000 euros."]
    assert [e[0] for e in spy.events] == ["tts_cloud_on_sensitive"]


def test_logged_excerpt_is_truncated(spy_manager, monkeypatch) -> None:
    """La base d'événements ne doit pas devenir une copie du texte sensible."""
    manager, spy = spy_manager
    monkeypatch.setattr(vm_module, "TTS_ALLOW_CLOUD_ON_SENSITIVE", False)
    monkeypatch.setattr(
        manager, "_synthesize_piper",
        lambda text, output_path=None: (_ for _ in ()).throw(PiperUnavailable("absent")),
    )

    long_text = "mon salaire " + "x" * 500
    manager._synthesize_routed(long_text, "")

    details = spy.events[0][1]
    max_length = vm_module.LOG_REASON_LENGTH + vm_module.LOG_EXCERPT_LENGTH + 5
    assert len(details) <= max_length
    assert "x" * 200 not in details
    # La raison ne doit pas manger tout le budget : l'extrait doit survivre.
    assert "mon salaire" in details


def test_playback_callback_fires_before_the_sound(spy_manager, monkeypatch) -> None:
    """
    La synthèse prend plusieurs secondes avec edge_tts, qui passe par le
    réseau. Sans ce signal, l'UI afficherait un avatar en train de parler
    pendant un silence.
    """
    manager, _spy = spy_manager
    order: list[str] = []
    monkeypatch.setattr(manager, "play_audio", lambda path: order.append("son"))

    manager.speak("bonjour", "", on_playback_start=lambda: order.append("signal"))

    assert order == ["signal", "son"]


def test_no_playback_callback_when_nothing_is_spoken(spy_manager, monkeypatch) -> None:
    """Contenu sensible non prononcé : l'avatar ne doit pas parler."""
    manager, _spy = spy_manager
    monkeypatch.setattr(vm_module, "TTS_ALLOW_CLOUD_ON_SENSITIVE", False)
    monkeypatch.setattr(
        manager, "_synthesize_piper",
        lambda text, output_path=None: (_ for _ in ()).throw(PiperUnavailable("absent")),
    )
    fired: list[bool] = []

    assert manager.speak("mon budget", "", on_playback_start=lambda: fired.append(True)) is None
    assert fired == []


def test_speak_returns_none_when_nothing_spoken(spy_manager, monkeypatch) -> None:
    """speak() doit signaler à l'UI qu'il n'y a pas eu de son."""
    manager, _spy = spy_manager
    monkeypatch.setattr(vm_module, "TTS_ALLOW_CLOUD_ON_SENSITIVE", False)
    monkeypatch.setattr(
        manager, "_synthesize_piper",
        lambda text, output_path=None: (_ for _ in ()).throw(PiperUnavailable("absent")),
    )
    monkeypatch.setattr(manager, "play_audio", lambda path: True)

    assert manager.speak("mon budget est serré", "") is None


# ── Libération du fichier audio ───────────────────────────────────────

def test_audio_file_is_released_after_playback(monkeypatch) -> None:
    """
    Sans unload(), pygame garde le fichier ouvert et la synthèse suivante
    échoue sur « [Errno 13] Permission denied ». Le bug frappait dès le
    second message — donc à chaque usage réel.
    """
    calls: list[str] = []

    class _FakeMusic:
        @staticmethod
        def load(path):
            calls.append("load")

        @staticmethod
        def play():
            calls.append("play")

        @staticmethod
        def get_busy():
            return False

        @staticmethod
        def stop():
            calls.append("stop")

        @staticmethod
        def unload():
            calls.append("unload")

    class _FakeMixer:
        music = _FakeMusic

        @staticmethod
        def get_init():
            return True

    fake_pygame = SimpleNamespace(mixer=_FakeMixer, time=SimpleNamespace(Clock=lambda: None))
    monkeypatch.setitem(__import__("sys").modules, "pygame", fake_pygame)

    VoiceManager().play_audio("data/output.mp3")
    assert "unload" in calls, "le fichier doit être libéré après lecture"


def test_audio_is_released_even_when_playback_fails(monkeypatch) -> None:
    """Une lecture qui échoue ne doit pas laisser le fichier verrouillé."""
    calls: list[str] = []

    class _BrokenMusic:
        @staticmethod
        def load(path):
            raise RuntimeError("format illisible")

        @staticmethod
        def stop():
            calls.append("stop")

        @staticmethod
        def unload():
            calls.append("unload")

    fake_pygame = SimpleNamespace(
        mixer=SimpleNamespace(music=_BrokenMusic, get_init=lambda: True),
        time=SimpleNamespace(Clock=lambda: None),
    )
    monkeypatch.setitem(__import__("sys").modules, "pygame", fake_pygame)

    assert VoiceManager().play_audio("x.mp3") is False
    assert "unload" in calls


def test_mixer_is_not_reinitialised_while_playing(monkeypatch) -> None:
    """Réinitialiser le mixer à chaque lecture coupe le son en cours."""
    inits: list[str] = []

    fake_pygame = SimpleNamespace(
        mixer=SimpleNamespace(
            music=SimpleNamespace(
                load=lambda p: None, play=lambda: None, get_busy=lambda: False,
                stop=lambda: None, unload=lambda: None,
            ),
            get_init=lambda: True,
            init=lambda: inits.append("init"),
        ),
        time=SimpleNamespace(Clock=lambda: None),
    )
    monkeypatch.setitem(__import__("sys").modules, "pygame", fake_pygame)

    VoiceManager().play_audio("x.mp3")
    assert inits == [], "le mixer déjà initialisé ne doit pas être relancé"


# ── Chaîne complète jusqu'à la base ───────────────────────────────────

def test_event_reaches_the_database(tmp_path, monkeypatch) -> None:
    """
    Vérifie la chaîne réelle VoiceManager -> LucasCore.log_event ->
    MemoryManager.save_event -> table system_events. Les mocks des tests
    précédents ne prouvent que l'appel, pas l'écriture.

    Base temporaire : on ne touche pas à lucas_memory.db.
    """
    from memory.memory_manager import MemoryManager

    memory = MemoryManager(db_path=tmp_path / "test_memory.db")
    manager = VoiceManager(log_event=memory.save_event)

    monkeypatch.setattr(vm_module, "TTS_ALLOW_CLOUD_ON_SENSITIVE", False)
    monkeypatch.setattr(
        manager, "_synthesize_piper",
        lambda text, output_path=None: (_ for _ in ()).throw(PiperUnavailable("absent")),
    )

    assert manager._synthesize_routed("Mon portfolio vaut 50000 euros.", "") is None

    rows = memory.cursor.execute(
        "SELECT event_type, details FROM system_events ORDER BY id DESC LIMIT 1"
    ).fetchall()
    memory.close()

    assert rows, "l'événement doit être écrit en base, pas seulement loggué en mémoire"
    assert rows[0][0] == "tts_skipped_sensitive"
    assert "portfolio" in rows[0][1]


# ── Câblage UI ────────────────────────────────────────────────────────

def test_tts_worker_passes_question_and_logger(monkeypatch) -> None:
    """
    Le TTSWorker doit transmettre la question au routeur : sans elle,
    « quel est mon salaire ? » -> « 3200 euros » repartirait vers le cloud.
    """
    pytest.importorskip("PySide6")
    from ui.main_window import TTSWorker

    received: dict[str, object] = {}

    class FakeVoiceManager:
        def __init__(self, log_event=None):
            received["log_event"] = log_event

        def speak(self, text, question="", on_playback_start=None):
            received["text"] = text
            received["question"] = question
            received["on_playback_start"] = on_playback_start
            return "data/output_piper.wav"

    monkeypatch.setattr("ui.main_window.VoiceManager", FakeVoiceManager)

    def logger(event_type: str, details: str = "") -> None:
        pass

    worker = TTSWorker("Il est de 3200 euros.", "quel est mon salaire ?", logger)
    worker.run()

    assert received["question"] == "quel est mon salaire ?"
    assert received["log_event"] is logger
    assert received["on_playback_start"] is not None, (
        "l'UI doit être prévenue du démarrage réel du son"
    )


# ── PiperEngine ───────────────────────────────────────────────────────

def test_missing_model_raises_piper_unavailable(tmp_path) -> None:
    engine = PiperEngine(voice="voix_inexistante", voices_dir=str(tmp_path))
    assert not engine.is_available()
    with pytest.raises(PiperUnavailable):
        engine.synthesize("test", str(tmp_path / "out.wav"))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
