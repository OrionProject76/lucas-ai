# modules/stt_engine.py — transcription audio locale (Speech-to-Text)
#
# ══════════════════════════════════════════════════════════════════════
# BRANCHÉ CÔTÉ SERVEUR le 02/08/2026 — EN USAGE RÉEL depuis (PWA S25 Ultra).
# ══════════════════════════════════════════════════════════════════════
# api/server.py appelle transcribe_base64() sur les messages WebSocket de
# type « audio » (voir websocket_endpoint). Le PC de Cyril n'a pas de
# micro (IDEAS.md #69, VISION_LONG_TERME.md §2 Pilier 3) — c'est le S25
# Ultra qui capture et envoie l'audio via la PWA. Qualité mesurée et
# améliorée le 03/08/2026 (STT_MODEL_SIZE, voir config.py et ROADMAP.md
# §5.4) suite à un signalement réel de transcription imprécise.
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

from config import (
    STT_CACHE_SIZE,
    STT_MAX_NO_SPEECH_PROB,
    STT_MIN_SPEECH_SECONDS,
    STT_MODEL_SIZE,
)

SUPPORTED_LANGUAGES = ("fr", "en")


class STTUnavailable(Exception):
    """Aucun backend Whisper utilisable, ou transcription impossible."""


@dataclass
class TranscriptResult:
    """Résultat d'une transcription.

    ⚠️ `confidence` ne dit PAS ce que son nom laisse croire — précisé le
    13/08/2026 après une mesure (ROADMAP.md §5.98). Avec le backend
    faster-whisper, c'est `info.language_probability` : la probabilité que
    la LANGUE détectée soit la bonne. Rien sur la qualité de la
    transcription, rien sur la nature de la source.

    Conséquence mesurée : une voix de télévision passe le seuil sans
    difficulté (0,977 sur « Thank you. Good night. »), parce que sa langue
    est parfaitement identifiable. Le seuil ne filtre le silence (0,305)
    que parce que Whisper y hésite sur la langue, par accident.

    `no_speech_prob` et `speech_seconds` sont donc exposés à côté : eux
    répondent à « est-ce de la parole, et assez longue ? ». Aucun des
    trois ne répond à « est-ce Cyril qui parle » — c'est le mot
    d'adressage (core/voice_commands.py) qui s'en charge.
    """

    text: str
    language: str
    confidence: float
    duration_seconds: float
    segments: list[dict] = field(default_factory=list)
    # Moyenne des `no_speech_prob` de segment. Mesuré le 13/08/2026 :
    # silence 0,862 — parole 0,002 à 0,012. Deux ordres de grandeur
    # d'écart, d'où un seuil qui peut être posé loin des deux bords.
    no_speech_prob: float | None = None
    # Durée cumulée des segments de parole, distincte de
    # `duration_seconds` (durée de l'enregistrement entier) : trois
    # secondes d'audio dont 0,2 de parole sont une bribe, pas un tour.
    speech_seconds: float | None = None

    # ⚠️ `None` = NON MESURÉ, et se lit « on ne sait pas », jamais « c'est
    # mauvais ». Ces deux champs valaient d'abord 0.0 par défaut : un
    # backend qui ne les renseignerait pas aurait alors fait rejeter TOUS
    # les tours, micro muet sans un message — la panne silencieuse qu'on
    # passe ses journées à corriger ailleurs. Un test l'a montré avant
    # qu'elle n'atteigne Cyril (test_server, « un enregistrement valide ne
    # doit pas être avalé »). Les deux backends réels les renseignent
    # toujours ; un filtre ne doit pas dépendre d'une donnée manquante
    # pour se déclencher.

    @property
    def is_confident(self) -> bool:
        """
        Seuil bas assumé : Whisper est prudent sur du français bruité, et
        un seuil trop haut ferait ignorer des phrases correctes.

        ⚠️ Ne protège que du silence, pas d'une source sonore tierce —
        voir la docstring de la classe. Conservé tel quel : il élimine
        réellement le silence, ce qu'aucun des deux autres critères ne
        rend inutile.
        """
        return self.confidence >= 0.6

    @property
    def is_speech(self) -> bool:
        """Vrai si Whisper a bien entendu de la parole, pas du bruit.

        Vrai aussi quand la mesure est absente — voir la note ci-dessus.
        """
        if self.no_speech_prob is None:
            return True
        return self.no_speech_prob <= STT_MAX_NO_SPEECH_PROB

    @property
    def has_enough_speech(self) -> bool:
        """Vrai si la parole dure assez pour être un tour, pas une bribe.

        Vrai aussi quand la mesure est absente — voir la note ci-dessus.
        """
        if self.speech_seconds is None:
            return True
        return self.speech_seconds >= STT_MIN_SPEECH_SECONDS

    def is_language(self, expected: str) -> bool:
        """Vrai si la langue détectée est celle attendue (ex. « fr »)."""
        return (self.language or "").lower() == expected.lower()


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
        # `no_speech_prob` est porté par CHAQUE segment, jamais globalement
        # — d'où la moyenne. Relevé dans la MÊME passe que `collected` :
        # `segments` est un générateur, il ne se relit pas deux fois.
        #
        # Gardé HORS de `collected` : la forme des dictionnaires de segment
        # est un contrat déjà utilisé ailleurs, et cette métrique n'a
        # d'intérêt qu'agrégée.
        collected: list[dict] = []
        probs: list[float] = []
        for s in segments:
            collected.append({"start": s.start, "end": s.end, "text": s.text})
            prob = getattr(s, "no_speech_prob", None)
            if prob is not None:
                probs.append(float(prob))
        text = "".join(s["text"] for s in collected).strip()
        # Aucun segment = rien à transcrire. 1.0 (« pas de parole ») plutôt
        # que 0.0, qui affirmerait exactement l'inverse de ce qu'on sait.
        no_speech = sum(probs) / len(probs) if probs else 1.0
        speech = sum(
            float(s["end"]) - float(s["start"])
            for s in collected
            if s["start"] is not None and s["end"] is not None
        )
        return TranscriptResult(
            text=text,
            language=info.language,
            confidence=float(info.language_probability),
            duration_seconds=float(info.duration),
            segments=collected,
            no_speech_prob=float(no_speech),
            speech_seconds=float(speech),
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
        # Ce backend expose déjà `no_speech_prob` par segment — la même
        # moyenne que ci-dessus, ici seulement réutilisée telle quelle au
        # lieu d'être retournée sous forme inversée.
        no_speech = sum(probabilities) / len(probabilities) if probabilities else 1.0
        speech = sum(
            float(s.get("end", 0.0)) - float(s.get("start", 0.0)) for s in segments
        )
        return TranscriptResult(
            text=raw.get("text", "").strip(),
            language=raw.get("language", "??"),
            confidence=float(confidence),
            duration_seconds=float(duration),
            segments=segments,
            no_speech_prob=float(no_speech),
            speech_seconds=float(speech),
        )
