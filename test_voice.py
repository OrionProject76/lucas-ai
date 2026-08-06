from modules.voice_manager import VoiceManager


def test_synthesis():
    voice_manager = VoiceManager()
    text = "Bonjour Cyril, je suis Luca's. Comment puis-je vous aider aujourd'hui ?"
    voice_manager.synthesize(text)
    voice_manager.play_audio("data/output.mp3")

if __name__ == "__main__":
    try:
        test_synthesis()
    except Exception as e:  # noqa: BLE001 — script de démonstration manuel :
        # afficher la panne est tout ce qu'on attend, un traceback brut
        # n'apprendrait rien de plus ici.
        print(f"Erreur de synthèse vocale : {e}")
