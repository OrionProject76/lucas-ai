# modules/vision_manager.py — capture d'écran et analyse par un VLM local
#
# ⚠️ Une capture d'écran est la donnée la plus sensible que Luca's
# manipule : elle peut contenir un relevé bancaire, un mot de passe
# affiché, une conversation privée. Elle ne quitte donc JAMAIS la
# machine — l'analyse passe par Ollama en local (llava par défaut),
# jamais par une API cloud. Voir CLAUDE.md règle 3.

import base64
from pathlib import Path

from PIL import ImageGrab

try:
    import ollama
except ImportError:  # le module reste importable sans Ollama installé
    ollama = None  # type: ignore[assignment]

DEFAULT_PROMPT = "Décris ce que tu vois sur cette image en français."


class VisionManager:
    """Capture l'écran et le fait décrire par un modèle vision local."""

    def __init__(self, model: str = "llava") -> None:
        self.model = model
        self.screenshot_path = "data/screenshot.png"

    def capture_screen(self, output_path: str | None = None) -> str:
        """
        Capture l'écran et retourne le chemin du fichier.

        Le répertoire parent est créé au besoin : sans ça, un data/ absent
        faisait échouer la capture sur un FileNotFoundError peu parlant.
        """
        output_path = output_path or self.screenshot_path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        screenshot = ImageGrab.grab()
        screenshot.save(output_path)
        return output_path

    def analyze_image(self, image_path: str, prompt: str = DEFAULT_PROMPT) -> str:
        """
        Décrit une image via Ollama en local.

        Retourne toujours une chaîne, jamais d'exception : un VLM
        indisponible ne doit pas faire tomber l'appelant (UI ou daemon).
        """
        if ollama is None:
            return "Module ollama non installé. Installez-le avec : pip install ollama"

        try:
            image_bytes = Path(image_path).read_bytes()
        except OSError as e:
            return f"Image illisible ({image_path}) : {e}"

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        try:
            response = ollama.chat(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": prompt,
                    "images": [image_base64],
                }],
            )
            return response["message"]["content"]
        except Exception as e:  # noqa: BLE001 — voir docstring
            return (
                f"Erreur analyse (modèle {self.model} peut-être non installé) : {e}\n"
                f"Installez-le avec : ollama pull {self.model}"
            )

    def see_and_describe(self, prompt: str = DEFAULT_PROMPT) -> str:
        """Capture puis analyse, en un appel."""
        return self.analyze_image(self.capture_screen(), prompt)


if __name__ == "__main__":
    vm = VisionManager()
    print("Capture...")
    path = vm.capture_screen()
    print(f"Sauvegardée : {path}")
    print("\nAnalyse...")
    print(f"Luca's voit : {vm.analyze_image(path)}")
