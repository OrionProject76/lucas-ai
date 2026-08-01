# modules/stt_manager.py — façade STT pour l'API et le mobile
#
# Le vrai moteur est dans modules/stt_engine.py. Ce fichier reste le
# point d'entrée historique, celui que l'API appellera quand le S25 Ultra
# enverra de l'audio (Phase 5). Il conserve la signature du stub
# d'origine, qui annonçait déjà ce chemin mobile.
#
# Il retourne des valeurs simples plutôt que des exceptions : côté API,
# une transcription impossible doit devenir une réponse lisible, pas une
# erreur 500.

from collections.abc import Callable

from modules.stt_engine import STTEngine, STTUnavailable, TranscriptResult


class STTManager:
    """Façade tolérante autour de STTEngine."""

    def __init__(self, log_event: Callable[[str, str], None] | None = None) -> None:
        self.engine = STTEngine(log_event=log_event)

    def is_available(self) -> bool:
        """Un backend Whisper est-il installé ?"""
        return self.engine.is_available()

    def transcribe(self, audio_path: str) -> TranscriptResult | None:
        """Transcrit un fichier. None si la transcription n'a pas pu tourner."""
        try:
            return self.engine.transcribe(audio_path)
        except STTUnavailable:
            return None

    def transcribe_from_mobile(self, audio_data: str) -> TranscriptResult | None:
        """
        Transcrit l'audio encodé en base64 envoyé par le S25 Ultra.

        C'est le chemin prévu depuis le début (voir le stub d'origine) :
        le PC n'ayant pas de micro, le téléphone est le capteur.
        """
        try:
            return self.engine.transcribe_base64(audio_data)
        except STTUnavailable:
            return None
