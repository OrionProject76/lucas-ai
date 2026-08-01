# modules/piper_engine.py — synthèse vocale 100 % locale via Piper
#
# Isolé de VoiceManager pour que celui-ci reste lisible : ici on ne fait que
# charger un modèle .onnx et produire un WAV. Aucune décision de routage.

import wave
from pathlib import Path

from config import PIPER_VOICE, PIPER_VOICES_DIR


class PiperUnavailable(Exception):
    """
    Piper ne peut pas prononcer : modèle absent, illisible, ou erreur de
    synthèse. C'est cette exception qui déclenche la logique de repli de
    VoiceManager — et donc, sur du contenu sensible, le silence.
    """


class PiperEngine:
    """Moteur TTS local. Le modèle est chargé au premier usage, puis gardé."""

    def __init__(self, voice: str | None = None, voices_dir: str | None = None) -> None:
        self.voice = voice or PIPER_VOICE
        self.voices_dir = Path(voices_dir or PIPER_VOICES_DIR)
        self._loaded_voice = None  # cache : le modèle fait ~60-75 Mo

    @property
    def model_path(self) -> Path:
        return self.voices_dir / f"{self.voice}.onnx"

    def is_available(self) -> bool:
        """Le modèle existe-t-il sur le disque ? (ne le charge pas)"""
        return self.model_path.is_file()

    def _load(self):
        """Charge le modèle une seule fois. Lève PiperUnavailable si impossible."""
        if self._loaded_voice is not None:
            return self._loaded_voice

        if not self.is_available():
            raise PiperUnavailable(
                f"Modèle Piper introuvable : {self.model_path}. "
                f"Télécharger avec : python -m piper.download_voices {self.voice} "
                f"--download-dir {self.voices_dir}"
            )

        try:
            from piper import PiperVoice

            self._loaded_voice = PiperVoice.load(self.model_path)
        except Exception as exc:  # paquet absent, modèle corrompu, etc.
            raise PiperUnavailable(f"Chargement de Piper impossible : {exc}") from exc

        return self._loaded_voice

    def synthesize(self, text: str, output_path: str) -> str:
        """
        Génère un WAV à partir du texte. Retourne le chemin du fichier.
        Lève PiperUnavailable en cas d'échec — jamais de repli silencieux
        vers un autre moteur, c'est à l'appelant de décider.
        """
        voice = self._load()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            with wave.open(output_path, "wb") as wav_file:
                voice.synthesize_wav(text, wav_file)
        except Exception as exc:
            raise PiperUnavailable(f"Synthèse Piper échouée : {exc}") from exc

        return output_path
