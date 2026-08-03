# modules/voice_manager.py — synthèse vocale à double moteur
#
# edge_tts (cloud Microsoft) par défaut pour la qualité de voix ;
# Piper (local) forcé dès que le contenu est sensible.
# La décision appartient à core.router.route_voice() — voir CLAUDE.md règle 3.

import asyncio
from collections.abc import Callable

import edge_tts

from config import EDGE_TTS_VOICE, TTS_ALLOW_CLOUD_ON_SENSITIVE
from core.router import route_voice
from modules.piper_engine import PiperEngine, PiperUnavailable

# Message affiché à Cyril quand un texte sensible ne peut pas être prononcé.
SENSITIVE_SKIPPED_MESSAGE = (
    "[Voix] Contenu sensible et voix locale indisponible — non prononcé. "
    "Le texte reste lisible ci-dessus."
)

# Longueur max d'un extrait loggué : la base d'événements ne doit pas
# devenir une copie du contenu sensible qu'on refuse justement d'envoyer.
LOG_EXCERPT_LENGTH = 80
LOG_REASON_LENGTH = 60


class VoiceManager:
    """
    Point d'entrée unique du TTS. `speak()` route puis prononce.

    `log_event` est injecté (et non importé) : modules/ ne doit pas importer
    LucasCore, ça créerait un cycle. L'UI passe `lucas.log_event`.
    """

    def __init__(
        self,
        voice: str | None = None,
        log_event: Callable[[str, str], object] | None = None,
    ) -> None:
        self.voice = voice or EDGE_TTS_VOICE
        self.output_path = "data/output.mp3"
        self.piper_output_path = "data/output_piper.wav"
        self.log_event = log_event
        self.piper = PiperEngine()

    # ── Journalisation ────────────────────────────────────────────────

    def _log(self, event_type: str, text: str, reason: str = "") -> None:
        """
        Enregistre un événement TTS : la raison, puis un extrait tronqué du
        texte concerné. Les deux sont bornés séparément — sinon une raison
        verbeuse mange tout le budget et l'extrait disparaît.
        """
        if self.log_event is None:
            return

        excerpt = text[:LOG_EXCERPT_LENGTH]
        if len(text) > LOG_EXCERPT_LENGTH:
            excerpt += "…"

        details = f"{reason[:LOG_REASON_LENGTH]} | {excerpt}" if reason else excerpt
        self.log_event(event_type, details)

    # ── Moteurs ───────────────────────────────────────────────────────

    async def _synthesize_edge_async(self, text: str, output_path: str) -> str:
        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(output_path)
        return output_path

    def _synthesize_edge(self, text: str, output_path: str | None = None) -> str:
        """Synthèse cloud (Microsoft). Le texte quitte la machine."""
        output_path = output_path or self.output_path
        return asyncio.run(self._synthesize_edge_async(text, output_path))

    def _synthesize_piper(self, text: str, output_path: str | None = None) -> str:
        """Synthèse locale. Lève PiperUnavailable si le modèle manque."""
        return self.piper.synthesize(text, output_path or self.piper_output_path)

    # ── API publique ──────────────────────────────────────────────────

    def synthesize(self, text: str, output_path: str | None = None) -> str:
        """
        Synthèse sans routage — reste sur edge_tts, comme historiquement.
        Conservée pour compatibilité (test_voice.py, appels directs).
        Préférer speak(), qui applique la règle de sensibilité.
        """
        return self._synthesize_edge(text, output_path)

    def play_audio(self, audio_path: str) -> bool:
        """
        Joue le fichier audio, puis le libère.

        ⚠️ Le `unload()` final n'est pas une politesse : sans lui, pygame
        garde le fichier ouvert après lecture, et la synthèse suivante
        échoue sur « [Errno 13] Permission denied » en tentant de
        réécrire data/output.mp3. Le bug frappait dès le second message,
        donc à chaque usage réel.

        Le mixer n'est initialisé qu'une fois : le réinitialiser à chaque
        lecture coupe le son en cours.
        """
        try:
            import pygame

            if not pygame.mixer.get_init():
                pygame.mixer.init()

            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            return True
        except Exception as e:  # noqa: BLE001 — un souci audio ne doit
            # jamais faire tomber le thread TTS ni l'UI.
            print(f"Erreur lecture audio: {e}")
            return False
        finally:
            self._release_audio()

    @staticmethod
    def _release_audio() -> None:
        """Rend la main sur le fichier audio, quoi qu'il se soit passé."""
        try:
            import pygame

            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
        except Exception as e:  # noqa: BLE001 — libérer au mieux
            # Pas de silence complet : si la libération échoue, la
            # synthèse suivante butera sur un fichier verrouillé et il
            # faut pouvoir relier les deux.
            print(f"[Voix] Libération du fichier audio impossible : {e}")

    def speak(
        self,
        text: str,
        question: str = "",
        on_playback_start: Callable[[], None] | None = None,
    ) -> str | None:
        """
        Route puis prononce. Retourne le chemin audio joué, ou None si rien
        n'a été prononcé (contenu sensible + voix locale indisponible).

        `question` sert au routage : une réponse anodine à une question
        sensible reste sensible.

        `on_playback_start` est appelé juste avant que le son démarre.
        La synthèse prend du temps — plusieurs secondes avec edge_tts, qui
        passe par le réseau. Sans ce signal, l'appelant ne peut que
        supposer que Luca's parle dès l'appel, et afficherait un avatar en
        train de parler pendant un silence.
        """
        audio_path = self._synthesize_routed(text, question)
        if audio_path is None:
            return None
        if on_playback_start is not None:
            on_playback_start()
        self.play_audio(audio_path)
        return audio_path

    def synthesize_routed(self, text: str, question: str = "") -> str | None:
        """
        Route puis synthétise, SANS jouer le son.

        Pour un appelant qui joue l'audio ailleurs que sur cette machine —
        le pont mobile (api/server.py) renvoie le fichier au téléphone,
        qui le joue lui-même. `speak()` reste le bon choix pour une
        lecture locale (UI PySide6, `pygame.mixer` sur les haut-parleurs
        du PC) : jouer ici aussi ferait entendre Luca's sur le PC à
        chaque question posée depuis le téléphone.
        """
        return self._synthesize_routed(text, question)

    def _synthesize_routed(self, text: str, question: str = "") -> str | None:
        """Applique la règle de sensibilité et produit le fichier audio."""
        if route_voice(text, question) != "local":
            return self._synthesize_edge(text)

        try:
            return self._synthesize_piper(text)
        except PiperUnavailable as exc:
            if TTS_ALLOW_CLOUD_ON_SENSITIVE:
                # Cyril a explicitement levé la garde dans config.py.
                self._log("tts_cloud_on_sensitive", text, str(exc))
                return self._synthesize_edge(text)

            # Défaut : on ne prononce pas. Jamais de repli cloud sur du sensible.
            self._log("tts_skipped_sensitive", text, str(exc))
            return None

    def list_voices(self) -> list[str]:
        """Voix edge_tts françaises disponibles."""
        return [
            "fr-FR-HenriNeural",
            "fr-FR-DeniseNeural",
            "fr-FR-EloiseNeural",
        ]


if __name__ == "__main__":
    vm = VoiceManager()
    print("Voix edge disponibles:", vm.list_voices())
    print("Modèle Piper disponible:", vm.piper.is_available())
    vm.speak("Bonjour Cyril, je suis Luca's. Comment puis-je vous aider aujourd'hui ?")
