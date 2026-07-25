import asyncio
import edge_tts
import os

class VoiceManager:
    def __init__(self, voice="fr-FR-HenriNeural"):
        self.voice = voice
        self.output_path = "data/output.mp3"

    async def _synthesize_async(self, text, output_path=None):
        """Génère un fichier audio à partir du texte"""
        if output_path is None:
            output_path = self.output_path

        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(output_path)
        return output_path

    def synthesize(self, text, output_path=None):
        """Version synchrone de la synthèse"""
        return asyncio.run(self._synthesize_async(text, output_path))

    def play_audio(self, audio_path):
        """Joue le fichier audio avec pygame"""
        try:
            import pygame
            pygame.mixer.init()
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            return True
        except Exception as e:
            print(f"Erreur lecture audio: {e}")
            return False

    def speak(self, text):
        """Synthétise et joue le texte"""
        print(f"Orion dit: {text}")
        audio_path = self.synthesize(text)
        self.play_audio(audio_path)
        return audio_path

    def list_voices(self):
        """Liste les voix françaises disponibles"""
        return [
            "fr-FR-HenriNeural",
            "fr-FR-DeniseNeural",
            "fr-FR-EloiseNeural"
        ]

if __name__ == "__main__":
    vm = VoiceManager()
    print("Voix disponibles:", vm.list_voices())
    vm.speak("Bonjour Cyril, je suis Orion. Comment puis-je vous aider aujourd'hui ?")
