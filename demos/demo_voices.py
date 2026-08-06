# demos/demo_voices.py — comparer les voix à l'oreille
#
# Choisir une voix en éditant config.py puis en relançant l'application
# à chaque essai est pénible et rend la comparaison impossible : on ne
# retient pas le timbre d'une voix entendue trois minutes plus tôt.
#
# Ce script prononce LA MÊME phrase avec chaque voix disponible, à la
# suite. Trente secondes suffisent alors à trancher.
#
# Usage :
#   python demos/demo_voices.py
#   python demos/demo_voices.py "une autre phrase à tester"
#
# ⚠️ Les voix edge_tts passent par le réseau (Microsoft). Les voix Piper
# sont locales. C'est justement cette différence que le routeur de
# CLAUDE.md règle 3 arbitre : contenu sensible → Piper, toujours.

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import PIPER_VOICES_DIR
from modules.piper_engine import PiperEngine, PiperUnavailable
from modules.voice_manager import VoiceManager

# Phrase par défaut : assez longue pour juger le rythme et les liaisons,
# assez courte pour ne pas lasser sur cinq passages.
DEFAULT_SENTENCE = (
    "Bonjour Cyril. J'ai analysé ton écran et vérifié tes comptes. "
    "Tout est en ordre, il n'y a rien d'inquiétant."
)

EDGE_VOICES = [
    ("fr-FR-HenriNeural", "masculine, actuelle par défaut"),
    ("fr-FR-DeniseNeural", "féminine"),
    ("fr-FR-EloiseNeural", "féminine, plus jeune"),
]


def _available_piper_voices() -> list[tuple[str, str]]:
    """Voix Piper réellement téléchargées, d'après les fichiers .onnx."""
    folder = Path(PIPER_VOICES_DIR)
    if not folder.is_dir():
        return []
    return [(model.stem, "locale") for model in sorted(folder.glob("*.onnx"))]


def _play_edge(voice: str, sentence: str, output: Path) -> bool:
    manager = VoiceManager(voice=voice)
    try:
        manager._synthesize_edge(sentence, str(output))
    except Exception as e:
        # pas interrompre la comparaison des autres.
        print(f"    échec : {e}")
        return False
    return manager.play_audio(str(output))


def _play_piper(voice: str, sentence: str, output: Path) -> bool:
    try:
        PiperEngine(voice=voice).synthesize(sentence, str(output))
    except PiperUnavailable as e:
        print(f"    échec : {e}")
        return False
    return VoiceManager().play_audio(str(output))


def main() -> None:
    sentence = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SENTENCE
    workspace = Path(tempfile.mkdtemp())

    print(f"Phrase testée :\n  « {sentence} »\n")

    print("── Voix cloud (edge_tts, Microsoft) ──")
    for voice, note in EDGE_VOICES:
        print(f"  {voice}  ({note})")
        _play_edge(voice, sentence, workspace / f"{voice}.mp3")

    piper_voices = _available_piper_voices()
    if piper_voices:
        print("\n── Voix locales (Piper) ──")
        for voice, note in piper_voices:
            print(f"  {voice}  ({note})")
            _play_piper(voice, sentence, workspace / f"{voice}.wav")
    else:
        print("\nAucune voix Piper téléchargée.")
        print("  python -m piper.download_voices fr_FR-siwis-medium "
              f"--download-dir {PIPER_VOICES_DIR}")

    print("\nPour retenir une voix, renseigner dans config.py :")
    print("  EDGE_TTS_VOICE = « … »   pour la voix cloud")
    print("  PIPER_VOICE    = « … »   pour la voix locale")


if __name__ == "__main__":
    main()
