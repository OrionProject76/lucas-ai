import os
from PIL import ImageGrab
import ollama

class VisionManager:
    def __init__(self):
        pass

    def capture_screen(self, output_path="data/screenshot.png"):
        try:
            img = ImageGrab.grab()
            img.save(output_path)
            return True
        except Exception as e:
            print(f"Erreur de capture d'écran : {e}")
            return False

    def analyze_image(self, image_path):
        try:
            model_name = "llava"
            ollama_model = ollama.load(model_name)
            description = ollama_model.describe(image_path)
            return description
        except Exception as e:
            print(f"Erreur d'analyse vision : {e}")
            return None

    def see_and_describe(self):
        if self.capture_screen():
            description = self.analyze_image("data/screenshot.png")
            return description
        else:
            return None

    def gestion_erreurs(self, erreur):
        if erreur == "modèle vision non disponible":
            print("Le modèle vision n'est pas installé. Veuillez installer le modèle llava via ollama pull llava.")
        elif erreur == "échec de capture":
            print("Erreur de capture d'écran. Veuillez vérifier les permissions et la configuration du système.")
