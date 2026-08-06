from modules.voice_manager import VoiceManager


def test_synthesis():
    voice_manager = VoiceManager()
    text = "Bonjour Cyril, je suis Luca's. Comment puis-je vous aider aujourd'hui ?"
    voice_manager.synthesize(text)
    voice_manager.play_audio("data/output.mp3")

if __name__ == "__main__":
    try:
        test_synthesis()
    except Exception as e:
        print(f"Erreur de synthèse vocale : {e}")
