# test_piper_engine.py — modules/piper_engine.py n'avait aucun test
# direct (trouvé via mesure de couverture réelle, Priorité 3 qualité/
# fiabilité, 04/08/2026) : PiperEngine est utilisé via VoiceManager
# ailleurs, mais jamais testé lui-même — en particulier _load() (le vrai
# appel à PiperVoice.load()) et synthesize() (l'écriture WAV réelle)
# n'étaient jamais exercés, seulement leur absence (is_available=False).

from __future__ import annotations

import pytest

from modules.piper_engine import PiperEngine, PiperUnavailable


@pytest.fixture
def engine(tmp_path):
    return PiperEngine(voice="test_voice", voices_dir=str(tmp_path))


def test_is_available_false_when_model_missing(engine) -> None:
    assert not engine.is_available()


def test_is_available_true_when_model_present(engine, tmp_path) -> None:
    (tmp_path / "test_voice.onnx").write_bytes(b"")
    assert engine.is_available()


def test_load_raises_a_clear_error_naming_the_download_command(engine) -> None:
    with pytest.raises(PiperUnavailable, match="python -m piper.download_voices"):
        engine._load()


def test_load_wraps_a_real_loading_failure(engine, tmp_path, monkeypatch) -> None:
    (tmp_path / "test_voice.onnx").write_bytes(b"")

    def _raise(*a, **k):
        raise RuntimeError("modèle corrompu")

    monkeypatch.setattr("piper.PiperVoice.load", staticmethod(_raise))

    with pytest.raises(PiperUnavailable, match="Chargement de Piper impossible"):
        engine._load()


def test_load_caches_the_voice_after_first_success(engine, tmp_path, monkeypatch) -> None:
    (tmp_path / "test_voice.onnx").write_bytes(b"")
    calls = []

    def _fake_load(*a, **k):
        calls.append(1)
        return "vraie-voix-chargee"

    monkeypatch.setattr("piper.PiperVoice.load", staticmethod(_fake_load))

    first = engine._load()
    second = engine._load()

    assert first == second == "vraie-voix-chargee"
    assert len(calls) == 1, "un modèle déjà chargé ne doit pas être rechargé"


def test_synthesize_writes_through_the_loaded_voice(engine, tmp_path, monkeypatch) -> None:
    (tmp_path / "test_voice.onnx").write_bytes(b"")

    class _FakeVoice:
        def synthesize_wav(self, text, wav_file):
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(b"\x00\x00")

    monkeypatch.setattr("piper.PiperVoice.load", staticmethod(lambda *a, **k: _FakeVoice()))

    output = tmp_path / "out.wav"
    result = engine.synthesize("bonjour", str(output))

    assert result == str(output)
    assert output.exists()


def test_synthesize_wraps_a_synthesis_failure(engine, tmp_path, monkeypatch) -> None:
    (tmp_path / "test_voice.onnx").write_bytes(b"")

    class _BrokenVoice:
        def synthesize_wav(self, text, wav_file):
            raise RuntimeError("texte illisible par le modèle")

    monkeypatch.setattr("piper.PiperVoice.load", staticmethod(lambda *a, **k: _BrokenVoice()))

    with pytest.raises(PiperUnavailable, match="Synthèse Piper échouée"):
        engine.synthesize("bonjour", str(tmp_path / "out.wav"))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
