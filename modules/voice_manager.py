import os
from edge_tts import EdgeTTS
import pygame.mixer

class VoiceManager:
    def __init__(self):
        self.edge_tts = None

    def synthesize(self, text, output_path="data/output.mp3"):
        try:
            if not self.edge_tts:
                self.edge_tts = EdgeTTS()
            self.edge_tts.synthesize_to_file(text, output_path)
        except Exception as e:
            print(f"Erreur de synthèse vocale : {e}")

    def play_audio(self, audio_path):
        try:
            pygame.mixer.init()
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()
        except Exception as e:
            print(f"Erreur de lecture du fichier audio : {e}")

    def list_voices(self):
        return ["fr-FR-HenriNeural", "fr-FR-DeniseNeural"]
