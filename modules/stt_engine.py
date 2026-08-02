# modules/stt_engine.py — transcription audio locale (Speech-to-Text)
#
# ══════════════════════════════════════════════════════════════════════
# BRANCHÉ CÔTÉ SERVEUR le 02/08/2026 — TOUJOURS SANS CLIENT RÉEL.
# ══════════════════════════════════════════════════════════════════════
# api/server.py appelle maintenant transcribe_base64() sur les messages
# WebSocket de type « audio » (voir websocket_endpoint). Ce module reste
# néanmoins SANS UTILISATION RÉELLE : le PC de Cyril n'a pas de micro
# (IDEAS.md #69, VISION_LONG_TERME.md §2 Pilier 3), et aucun client mobile
# n'existe encore pour envoyer de l'audio — seul le CÔTÉ SERVEUR du pont
# est prêt. Ne pas le compter comme une fonctionnalité utilisable avant
# qu'un vrai client (PWA S25 Ultra) existe et soit testé en conditions
# réelles.
#
# faster-whisper installé le 02/08/2026 (~200 Mo, sans torch — voir le
# choix de backend ci-dessous). openai-whisper reste un repli possible
# si faster-whisper manque sur une autre machine.
#
# ⚠️ L'audio est la donnée la plus intrusive que Luca's puisse traiter :
# il capte tout ce qui se dit dans la pièce, pas seulement ce qui lui est
# adressé. Il ne quitte JAMAIS la machine — la transcription tourne en
# local, aucun service tiers n'est appelé. Voir CLAUDE.md règle 3.
#
# ── Ce module ne capte pas le micro, et c'est volontaire ──────────────
# Le PC de Cyril n'a pas de microphone : contrainte matérielle actée dans
# VISION_LONG_TERME.md §2, Pilier 3. C'est le S25 Ultra qui sert de
# capteur, et qui enverra l'audio via l'API (Phase 4). Ce moteur
# transcrit donc ce qu'on lui donne — fichier, tableau numpy ou base64 —
# et ne suppose aucun périphérique local.
#
# ── Backend ───────────────────────────────────────────────────────────
# Deux implémentations de Whisper sont acceptées, essayées dans l'ordre.
# Aucune n'est requise à l'import : le module reste testable sans, comme
# PiperEngine sans ses modèles de voix.

import base64
import tempfile
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from config import STT_CACHE_SIZE, STT_MODEL_SIZE

SUPPORTED_LANGUAGES = ("fr", "en")


class STTUnavailable(Exception):
    """Aucun backend Whisper utilisable, ou transcription impossible."""


@dataclass
class TranscriptResult:
    """Résultat d'une transcription."""

    text: str
    language: str
    confidence: float
    duration_seconds: float
    segments: list[dict] = field(default_factory=list)

    @property
    def is_confident(self) -> bool:
        """
        Seuil bas assumé : Whisper est prudent sur du français bruité, et
        un seuil trop haut ferait ignorer des phrases correctes.
        """
        return self.confidence >= 0.6


class STTEngine:
    """
    Transcrit de l'audio en texte, en local.

    `log_event` est injecté comme ailleurs : modules/ ne connaît pas
    LucasCore.
    """

    def __init__(
        self,
        model_size: str | None = None,
        log_event: Callable[[str, str], None] | None = None,
        backend=None,
    ) -> None:
        self.model_size = model_size or STT_MODEL_SIZE
        self.log_event = log_event
        self._backend = backend  # injecté dans les tests
        self._model = None
        # Cache borné : re-transcrire deux fois le même extrait coûte
        # plusieurs secondes de GPU pour un résultat identique.
        self._cache: OrderedDict[str, TranscriptResult] = OrderedDict()

    # ── Backend ───────────────────────────────────────────────────────

    def _load_backend(self):
        """
        Charge le premier backend Whisper disponible.

        faster-whisper d'abord : même qualité, ~4× plus rapide, et sans
        torch — ce qui compte ici, la RTX 5080 étant déjà partagée avec
        les modèles Ollama (VISION_LONG_TERME.md §3).
        """
        if self._backend is not None:
            return self._backend

        try:
            from faster_whisper import WhisperModel

            self._backend = _FasterWhisperBackend(WhisperModel, self.model_size)
            return self._backend
        except ImportError:
            pass

        try:
            import whisper

            self._backend = _OpenAIWhisperBackend(whisper, self.model_size)
            return self._backend
        except ImportError as exc:
            raise STTUnavailable(
                "Aucun backend Whisper installé. Installer au choix :\n"
                "  pip install faster-whisper   (léger, recommandé)\n"
                "  pip install openai-whisper   (tire torch, ~2,5 Go)"
            ) from exc

    def is_available(self) -> bool:
        try:
            self._load_backend()
        except STTUnavailable:
            return False
        return True

    # ── Transcription ─────────────────────────────────────────────────

    def transcribe(self, audio) -> TranscriptResult:
        """
        Transcrit un fichier (chemin) ou un tableau numpy.

        Lève STTUnavailable plutôt que de retourner un texte vide : un
        appelant doit pouvoir distinguer « rien n'a été dit » de « la
        transcription n'a pas pu tourner ».
        """
        cache_key = self._cache_key(audio)
        if cache_key is not None and cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        backend = self._load_backend()

        try:
            result = backend.transcribe(audio)
        except Exception as exc:
            raise STTUnavailable(f"Transcription impossible : {exc}") from exc

        if result.language not in SUPPORTED_LANGUAGES:
            self._log("stt_unexpected_language", result.language)

        if cache_key is not None:
            self._remember(cache_key, result)
        return result

    def transcribe_base64(self, audio_data: str, suffix: str = ".wav") -> TranscriptResult:
        """
        Transcrit de l'audio encodé en base64 — le format qu'enverra le
        S25 Ultra via l'API.

        Le fichier temporaire est supprimé quoi qu'il arrive : un extrait
        de conversation ne doit pas traîner dans le dossier temp.
        """
        try:
            raw = base64.b64decode(audio_data, validate=True)
        except Exception as exc:
            raise STTUnavailable(f"Audio base64 illisible : {exc}") from exc

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(raw)
                temp_path = Path(tmp.name)
            return self.transcribe(str(temp_path))
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    # ── Cache ─────────────────────────────────────────────────────────

    @staticmethod
    def _cache_key(audio) -> str | None:
        """
        Clé de cache : le chemin du fichier. Les tableaux numpy ne sont
        pas mis en cache — les hacher coûterait autant que transcrire.
        """
        if isinstance(audio, (str, Path)):
            return str(audio)
        return None

    def _remember(self, key: str, result: TranscriptResult) -> None:
        self._cache[key] = result
        while len(self._cache) > STT_CACHE_SIZE:
            self._cache.popitem(last=False)

    def _log(self, event_type: str, details: str) -> None:
        if self.log_event is not None:
            self.log_event(event_type, details[:200])


# ── Adaptateurs de backend ────────────────────────────────────────────
#
# Chacun ramène la sortie de sa bibliothèque au même TranscriptResult,
# pour que STTEngine ignore laquelle est installée.


class _FasterWhisperBackend:
    def __init__(self, model_class, model_size: str) -> None:
        # ⚠️ CPU explicite, PAS "auto" (bug trouvé le 02/08/2026 en testant
        # le pont mobile de bout en bout, pas seulement avec des mocks) :
        # "auto" tente CUDA en premier sur cette machine (RTX 5080 détectée)
        # et échoue — "Library cublas64_12.dll is not found". Le commentaire
        # du module dit depuis le début que faster-whisper est choisi pour
        # tourner en CPU et ne pas se disputer la VRAM avec Ollama
        # (VISION_LONG_TERME.md §3) ; "auto" contredisait cette intention
        # documentée, indépendamment du plantage qu'il provoquait ici.
        self.model = model_class(model_size, device="cpu", compute_type="int8")

    def transcribe(self, audio) -> TranscriptResult:
        segments, info = self.model.transcribe(audio, language=None)
        collected = [
            {"start": s.start, "end": s.end, "text": s.text} for s in segments
        ]
        text = "".join(s["text"] for s in collected).strip()
        return TranscriptResult(
            text=text,
            language=info.language,
            confidence=float(info.language_probability),
            duration_seconds=float(info.duration),
            segments=collected,
        )


class _OpenAIWhisperBackend:
    def __init__(self, whisper_module, model_size: str) -> None:
        self.model = whisper_module.load_model(model_size)

    def transcribe(self, audio) -> TranscriptResult:
        raw = self.model.transcribe(audio)
        segments = raw.get("segments", [])
        # openai-whisper ne donne pas de score global : on approxime par
        # la moyenne des probabilités de segment, et on le documente
        # plutôt que de laisser croire à une mesure exacte.
        probabilities = [
            s.get("no_speech_prob") for s in segments if s.get("no_speech_prob") is not None
        ]
        confidence = 1.0 - (sum(probabilities) / len(probabilities)) if probabilities else 0.0
        duration = segments[-1].get("end", 0.0) if segments else 0.0
        return TranscriptResult(
            text=raw.get("text", "").strip(),
            language=raw.get("language", "??"),
            confidence=float(confidence),
            duration_seconds=float(duration),
            segments=segments,
        )
