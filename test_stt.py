# test_stt.py — moteur de transcription locale
#
# ⚠️ SOCLE PHASE 5, NON ACTIVÉ. Le module testé ici ne peut pas être
# alimenté aujourd'hui : le PC n'a pas de micro, la source audio sera le
# S25 Ultra via l'API (IDEAS.md #69). Ces tests valident la plomberie,
# pas une fonctionnalité livrée.
#
# Aucun backend Whisper n'est requis : ils sont injectés. Les tests
# tournent donc sans les 2,5 Go de torch, et vérifient précisément ce
# que le module garantit — dont le fait que l'audio ne sort jamais.

from __future__ import annotations

import base64
import inspect
import sys
from types import SimpleNamespace

import pytest

from modules import stt_engine as stt_module
from modules.stt_engine import STTEngine, STTUnavailable, TranscriptResult
from modules.stt_manager import STTManager


class _FakeBackend:
    """Backend injecté : renvoie un résultat fixe et compte les appels."""

    def __init__(self, result: TranscriptResult | None = None, raises=None) -> None:
        self.result = result or TranscriptResult(
            text="bonjour Luca's",
            language="fr",
            confidence=0.94,
            duration_seconds=1.8,
            segments=[{"start": 0.0, "end": 1.8, "text": "bonjour Luca's"}],
        )
        self.raises = raises
        self.calls: list = []

    def transcribe(self, audio) -> TranscriptResult:
        self.calls.append(audio)
        if self.raises:
            raise self.raises
        return self.result


# ── Transcription ─────────────────────────────────────────────────────

def test_transcribes_a_file() -> None:
    backend = _FakeBackend()
    result = STTEngine(backend=backend).transcribe("extrait.wav")

    assert result.text == "bonjour Luca's"
    assert result.language == "fr"
    assert backend.calls == ["extrait.wav"]


def test_failure_raises_rather_than_returning_empty_text() -> None:
    """
    L'appelant doit pouvoir distinguer « rien n'a été dit » de « la
    transcription n'a pas pu tourner ».
    """
    engine = STTEngine(backend=_FakeBackend(raises=RuntimeError("modèle corrompu")))
    with pytest.raises(STTUnavailable):
        engine.transcribe("extrait.wav")


def test_missing_backend_explains_how_to_install(monkeypatch) -> None:
    engine = STTEngine()
    monkeypatch.setitem(__import__("sys").modules, "faster_whisper", None)
    monkeypatch.setitem(__import__("sys").modules, "whisper", None)

    with pytest.raises(STTUnavailable, match="pip install"):
        engine.transcribe("extrait.wav")


def test_is_available_reflects_the_backend() -> None:
    assert STTEngine(backend=_FakeBackend()).is_available()


def test_unexpected_language_is_logged() -> None:
    """Une langue hors fr/en signale souvent un audio mal découpé."""
    events: list[tuple[str, str]] = []
    backend = _FakeBackend(TranscriptResult("hallo", "de", 0.8, 1.0))
    STTEngine(backend=backend, log_event=lambda t, d="": events.append((t, d))).transcribe("x.wav")
    assert [t for t, _ in events] == ["stt_unexpected_language"]


def test_expected_language_is_not_logged() -> None:
    events: list[tuple[str, str]] = []
    STTEngine(
        backend=_FakeBackend(), log_event=lambda t, d="": events.append((t, d))
    ).transcribe("x.wav")
    assert events == []


# ── Cache ─────────────────────────────────────────────────────────────

def test_identical_file_is_not_transcribed_twice() -> None:
    backend = _FakeBackend()
    engine = STTEngine(backend=backend)
    engine.transcribe("extrait.wav")
    engine.transcribe("extrait.wav")
    assert len(backend.calls) == 1, "la seconde demande doit venir du cache"


def test_different_files_are_both_transcribed() -> None:
    backend = _FakeBackend()
    engine = STTEngine(backend=backend)
    engine.transcribe("a.wav")
    engine.transcribe("b.wav")
    assert len(backend.calls) == 2


def test_cache_is_bounded(monkeypatch) -> None:
    """Sans borne, une session longue garderait tout l'audio en mémoire."""
    monkeypatch.setattr(stt_module, "STT_CACHE_SIZE", 3)
    backend = _FakeBackend()
    engine = STTEngine(backend=backend)
    for i in range(10):
        engine.transcribe(f"extrait_{i}.wav")
    assert len(engine._cache) == 3


def test_numpy_buffers_are_not_cached() -> None:
    """Hacher un tableau audio coûterait autant que le transcrire."""
    backend = _FakeBackend()
    engine = STTEngine(backend=backend)
    buffer = [0.1, 0.2, 0.3]
    engine.transcribe(buffer)
    engine.transcribe(buffer)
    assert len(backend.calls) == 2


# ── Chemin mobile (base64) ────────────────────────────────────────────

def test_base64_audio_is_transcribed() -> None:
    backend = _FakeBackend()
    engine = STTEngine(backend=backend)
    encoded = base64.b64encode(b"RIFF....WAVEfmt ").decode()

    result = engine.transcribe_base64(encoded)
    assert result.text == "bonjour Luca's"


def test_temporary_audio_file_is_always_deleted() -> None:
    """Un extrait de conversation ne doit pas traîner dans temp/."""
    backend = _FakeBackend()
    engine = STTEngine(backend=backend)
    engine.transcribe_base64(base64.b64encode(b"audio").decode())

    written_path = backend.calls[0]
    assert not __import__("pathlib").Path(written_path).exists()


def test_temporary_file_is_deleted_even_on_failure() -> None:
    backend = _FakeBackend(raises=RuntimeError("boum"))
    engine = STTEngine(backend=backend)

    with pytest.raises(STTUnavailable):
        engine.transcribe_base64(base64.b64encode(b"audio").decode())

    assert not __import__("pathlib").Path(backend.calls[0]).exists()


def test_invalid_base64_is_reported_clearly() -> None:
    engine = STTEngine(backend=_FakeBackend())
    with pytest.raises(STTUnavailable, match="base64"):
        engine.transcribe_base64("ceci n'est pas du base64 !!!")


# ── Résultat ──────────────────────────────────────────────────────────

def test_confidence_threshold() -> None:
    assert TranscriptResult("x", "fr", 0.9, 1.0).is_confident
    assert not TranscriptResult("x", "fr", 0.3, 1.0).is_confident


# ── Façade STTManager ─────────────────────────────────────────────────

def test_manager_returns_none_instead_of_raising(monkeypatch) -> None:
    """
    Côté API, une transcription impossible doit devenir une réponse
    lisible, pas une erreur 500.
    """
    manager = STTManager()
    monkeypatch.setattr(
        manager.engine, "transcribe",
        lambda audio: (_ for _ in ()).throw(STTUnavailable("pas de backend")),
    )
    assert manager.transcribe("x.wav") is None


def test_manager_forwards_the_mobile_path(monkeypatch) -> None:
    manager = STTManager()
    manager.engine._backend = _FakeBackend()
    assert manager.transcribe_from_mobile(base64.b64encode(b"a").decode()).language == "fr"


# ── Sélection du backend réel ──────────────────────────────────────────
#
# Tout ce qui précède injecte un backend factice : _load_backend() et les
# deux adaptateurs (_FasterWhisperBackend, _OpenAIWhisperBackend) n'étaient
# donc jamais exercés eux-mêmes. Trouvé via mesure de couverture réelle,
# même motif que piper_engine.py (backend réel jamais chargé, seule son
# absence l'était).

def test_load_backend_prefers_faster_whisper(monkeypatch) -> None:
    class _FakeWhisperModel:
        def __init__(self, model_size, device=None, compute_type=None):
            self.model_size = model_size
            self.device = device
            self.compute_type = compute_type

    fake_module = SimpleNamespace(WhisperModel=_FakeWhisperModel)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)

    engine = STTEngine(model_size="small")
    backend = engine._load_backend()

    assert isinstance(backend, stt_module._FasterWhisperBackend)
    assert backend.model.model_size == "small"
    assert backend.model.device == "cpu", "jamais 'auto' : voir le commentaire du module (bug cublas64_12.dll)"
    assert backend.model.compute_type == "int8"


def test_load_backend_falls_back_to_openai_whisper(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "faster_whisper", None)

    class _FakeModel:
        pass

    fake_whisper = SimpleNamespace(load_model=lambda model_size: _FakeModel())
    monkeypatch.setitem(sys.modules, "whisper", fake_whisper)

    backend = STTEngine(model_size="base")._load_backend()

    assert isinstance(backend, stt_module._OpenAIWhisperBackend)


def test_faster_whisper_backend_converts_segments_to_a_transcript_result() -> None:
    segments = [
        SimpleNamespace(start=0.0, end=0.8, text="bonjour "),
        SimpleNamespace(start=0.8, end=1.5, text="Luca's"),
    ]
    info = SimpleNamespace(language="fr", language_probability=0.91, duration=1.5)

    class _FakeModel:
        def transcribe(self, audio, language=None):
            assert language is None
            return segments, info

    backend = stt_module._FasterWhisperBackend.__new__(stt_module._FasterWhisperBackend)
    backend.model = _FakeModel()

    result = backend.transcribe("extrait.wav")

    assert result.text == "bonjour Luca's"
    assert result.language == "fr"
    assert result.confidence == pytest.approx(0.91)
    assert result.duration_seconds == pytest.approx(1.5)
    assert result.segments == [
        {"start": 0.0, "end": 0.8, "text": "bonjour "},
        {"start": 0.8, "end": 1.5, "text": "Luca's"},
    ]


def test_openai_whisper_backend_approximates_confidence_from_segments() -> None:
    """
    openai-whisper ne donne pas de score global : approximé par la moyenne
    des probabilités de segment (documenté comme une approximation, pas
    une mesure exacte).
    """
    raw = {
        "text": " bonjour Luca's ",
        "language": "fr",
        "segments": [
            {"end": 0.8, "no_speech_prob": 0.1},
            {"end": 1.5, "no_speech_prob": 0.3},
        ],
    }

    class _FakeModel:
        def transcribe(self, audio):
            return raw

    backend = stt_module._OpenAIWhisperBackend.__new__(stt_module._OpenAIWhisperBackend)
    backend.model = _FakeModel()

    result = backend.transcribe("extrait.wav")

    assert result.text == "bonjour Luca's"
    assert result.confidence == pytest.approx(1.0 - (0.1 + 0.3) / 2)
    assert result.duration_seconds == pytest.approx(1.5)


def test_openai_whisper_backend_handles_no_segments() -> None:
    """Pas de segment (silence complet) : ne pas diviser par zéro."""
    class _FakeModel:
        def transcribe(self, audio):
            return {"text": "", "language": "fr", "segments": []}

    backend = stt_module._OpenAIWhisperBackend.__new__(stt_module._OpenAIWhisperBackend)
    backend.model = _FakeModel()

    result = backend.transcribe("silence.wav")

    assert result.confidence == 0.0
    assert result.duration_seconds == 0.0


def test_cache_key_treats_path_objects_like_strings() -> None:
    from pathlib import Path

    assert STTEngine._cache_key(Path("extrait.wav")) == str(Path("extrait.wav"))


# ── Sécurité ──────────────────────────────────────────────────────────

def test_audio_never_leaves_the_machine() -> None:
    """
    L'audio capte tout ce qui se dit dans la pièce, pas seulement ce qui
    est adressé à Luca's. Aucun service tiers ne doit être appelé
    (CLAUDE.md règle 3).
    """
    source = inspect.getsource(stt_module)
    for forbidden in ("requests.", "urllib", "openai.", "api.openai.com", "ask_cloud"):
        assert forbidden not in source


def test_module_imports_without_any_whisper_backend() -> None:
    """
    Le module doit rester importable et testable sans les 2,5 Go de
    torch — même principe que PiperEngine sans ses modèles de voix.
    """
    assert STTEngine is not None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
