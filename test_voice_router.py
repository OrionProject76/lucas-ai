# test_voice_router.py — routage TTS local/cloud et garde sur le sensible
#
# Règle testée : un contenu sensible n'est jamais prononcé par edge_tts
# (donc jamais envoyé à Microsoft), sauf interrupteur explicite dans
# config.py. Voir CLAUDE.md règle 3, section TTS.
#
# Aucun appel réseau, aucun son joué : Piper et edge_tts sont mockés.

from __future__ import annotations

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


# ── PiperEngine ───────────────────────────────────────────────────────

def test_missing_model_raises_piper_unavailable(tmp_path) -> None:
    engine = PiperEngine(voice="voix_inexistante", voices_dir=str(tmp_path))
    assert not engine.is_available()
    with pytest.raises(PiperUnavailable):
        engine.synthesize("test", str(tmp_path / "out.wav"))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
