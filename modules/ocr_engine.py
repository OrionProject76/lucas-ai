# modules/ocr_engine.py — lecture du texte affiché à l'écran
#
# ── Pourquoi l'OCR est nécessaire ─────────────────────────────────────
#
# llava ne sait pas lire un écran. Mesuré sur des captures réelles, sa
# réponse était : « je ne peux pas vérifier le contenu exact du texte car
# il est trop petit pour être entièrement visible ». La cause est
# structurelle — le modèle redimensionne en interne vers ~336 px de côté,
# et une capture 3840×2160 y perd toute lisibilité. Un recadrage 1280×720
# ne change rien : c'est une limite du modèle sur du texte dense.
#
# Un VLM plus lourd (internvl2) corrigerait ça mais aggraverait la
# contention GPU avec Ollama — point de vigilance acté dans
# VISION_LONG_TERME.md §3. D'où l'OCR, qui tourne en CPU.
#
# Les deux se complètent et ne se remplacent pas : l'OCR donne le texte
# exact, le VLM dit quelle application est ouverte et comment l'écran est
# disposé. Voir LucasCore._describe_screen().
#
# ── Choix du moteur ───────────────────────────────────────────────────
#
# mission_01_screen_watcher.md prévoyait easyocr. Écarté : il tire torch
# (~2,5 Go) et utilise le GPU par défaut, soit exactement ce qu'on évite
# en refusant internvl2. RapidOCR tourne sur onnxruntime — déjà installé
# pour chromadb et Piper — en CPU, sans binaire externe.
# Mesuré : 2,8 s sur une capture 4K, ~1200 caractères extraits.
#
# ⚠️ SÉCURITÉ : le texte extrait est du VERBATIM d'écran — mot de passe
# affiché, relevé bancaire ouvert, conversation privée. C'est plus
# sensible que la description du VLM, qui paraphrase. Il n'est jamais
# journalisé, et une question qui déclenche la vision est forcée en local
# par route() (CLAUDE.md règle 3).

from dataclasses import dataclass, field
from pathlib import Path


class OCRUnavailable(Exception):
    """Aucun moteur OCR utilisable, ou extraction impossible."""


@dataclass
class OCRResult:
    """Texte lu à l'écran."""

    text: str
    lines: list[str] = field(default_factory=list)
    confidence: float = 0.0

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


class OCREngine:
    """
    Extrait le texte d'une image, en local.

    `backend` est injectable pour les tests : le module reste importable
    et testable sans moteur installé, comme PiperEngine sans ses modèles
    de voix.
    """

    def __init__(self, backend=None) -> None:
        self._backend = backend

    # ── Moteur ────────────────────────────────────────────────────────

    def _load_backend(self):
        """
        Charge le premier moteur disponible.

        RapidOCR d'abord : c'est celui qui n'impose ni torch ni binaire
        externe. pytesseract en second, s'il se trouve déjà là.
        """
        if self._backend is not None:
            return self._backend

        try:
            from rapidocr_onnxruntime import RapidOCR

            self._backend = _RapidOCRBackend(RapidOCR())
            return self._backend
        except ImportError:
            pass

        try:
            import pytesseract

            self._backend = _TesseractBackend(pytesseract)
            return self._backend
        except ImportError as exc:
            raise OCRUnavailable(
                "Aucun moteur OCR installé. Installer :\n"
                "  pip install rapidocr-onnxruntime   (CPU, recommandé)\n"
                "  pip install pytesseract            (nécessite le binaire Tesseract)"
            ) from exc

    def is_available(self) -> bool:
        try:
            self._load_backend()
        except OCRUnavailable:
            return False
        return True

    # ── Extraction ────────────────────────────────────────────────────

    def extract_text(self, image_path: str | Path) -> OCRResult:
        """
        Lit le texte d'une image.

        Lève OCRUnavailable en cas d'échec plutôt que de retourner un
        résultat vide : l'appelant doit pouvoir distinguer « aucun texte
        à l'écran » de « l'OCR n'a pas pu tourner ».
        """
        backend = self._load_backend()

        if not Path(image_path).is_file():
            raise OCRUnavailable(f"Image introuvable : {image_path}")

        try:
            return backend.extract(str(image_path))
        except Exception as exc:
            raise OCRUnavailable(f"Extraction impossible : {exc}") from exc


# ── Adaptateurs ───────────────────────────────────────────────────────
#
# Chacun ramène la sortie de sa bibliothèque au même OCRResult, pour que
# OCREngine ignore lequel est installé.


class _RapidOCRBackend:
    def __init__(self, engine) -> None:
        self.engine = engine

    def extract(self, image_path: str) -> OCRResult:
        # RapidOCR retourne (résultats, temps) ; chaque résultat est
        # [boîte, texte, confiance]. Aucun texte détecté donne None, pas
        # une liste vide — d'où le repli explicite.
        raw, _timings = self.engine(image_path)
        if not raw:
            return OCRResult(text="", lines=[], confidence=0.0)

        lines = [entry[1] for entry in raw]
        scores = [float(entry[2]) for entry in raw if len(entry) > 2]
        return OCRResult(
            text="\n".join(lines),
            lines=lines,
            confidence=sum(scores) / len(scores) if scores else 0.0,
        )


class _TesseractBackend:
    def __init__(self, pytesseract_module) -> None:
        self.pytesseract = pytesseract_module

    def extract(self, image_path: str) -> OCRResult:
        from PIL import Image

        from config import OCR_LANGUAGES

        # Tesseract attend « fra+eng », pas une liste.
        languages = "+".join(
            {"fr": "fra", "en": "eng"}.get(code, code) for code in OCR_LANGUAGES
        )
        text = self.pytesseract.image_to_string(Image.open(image_path), lang=languages)
        lines = [line for line in text.splitlines() if line.strip()]
        return OCRResult(
            text="\n".join(lines),
            lines=lines,
            # Tesseract ne donne pas de score global sans passer par
            # image_to_data ; on ne prétend pas en avoir un.
            confidence=0.0,
        )
