# test_ocr.py — lecture du texte affiché à l'écran
#
# llava ne sait pas lire un écran : il redimensionne en interne vers
# ~336 px, et une capture 4K y perd toute lisibilité. Mesuré sur des
# captures réelles, sa réponse était « le texte est trop petit pour être
# entièrement visible ». L'OCR comble ce trou en CPU.
#
# Aucun moteur OCR réel n'est sollicité ici : le backend est injecté.

from __future__ import annotations

import inspect
import sys
from types import SimpleNamespace

import pytest

from modules.ocr_engine import (
    OCREngine,
    OCRResult,
    OCRUnavailable,
    _RapidOCRBackend,
    _TesseractBackend,
)


class _FakeBackend:
    """Backend injecté : renvoie un résultat fixe et compte les appels."""

    def __init__(self, result: OCRResult | None = None, raises=None) -> None:
        self.result = result or OCRResult(
            text="Error: file not found\nligne suivante",
            lines=["Error: file not found", "ligne suivante"],
            confidence=0.93,
        )
        self.raises = raises
        self.calls: list[str] = []

    def extract(self, image_path: str) -> OCRResult:
        self.calls.append(image_path)
        if self.raises:
            raise self.raises
        return self.result


@pytest.fixture
def image(tmp_path):
    path = tmp_path / "capture.png"
    path.write_bytes(b"\x89PNG faux contenu")
    return str(path)


# ── Extraction ────────────────────────────────────────────────────────

def test_text_is_extracted(image) -> None:
    backend = _FakeBackend()
    result = OCREngine(backend=backend).extract_text(image)

    assert "Error: file not found" in result.text
    assert len(result.lines) == 2
    assert backend.calls == [image]


def test_missing_image_is_reported(tmp_path) -> None:
    engine = OCREngine(backend=_FakeBackend())
    with pytest.raises(OCRUnavailable, match="introuvable"):
        engine.extract_text(tmp_path / "absente.png")


def test_backend_failure_raises_rather_than_returning_empty(image) -> None:
    """
    L'appelant doit distinguer « aucun texte à l'écran » de « l'OCR n'a
    pas pu tourner » : dans le premier cas il se rabat sur le VLM, dans
    le second il faut le signaler.
    """
    engine = OCREngine(backend=_FakeBackend(raises=RuntimeError("modèle corrompu")))
    with pytest.raises(OCRUnavailable):
        engine.extract_text(image)


def test_missing_engine_explains_how_to_install(image, monkeypatch) -> None:
    import sys

    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", None)
    monkeypatch.setitem(sys.modules, "pytesseract", None)

    with pytest.raises(OCRUnavailable, match="pip install"):
        OCREngine().extract_text(image)


def test_empty_result_is_detected() -> None:
    assert OCRResult(text="   ").is_empty
    assert not OCRResult(text="du texte").is_empty


def test_is_available_reflects_the_backend() -> None:
    assert OCREngine(backend=_FakeBackend()).is_available()


def test_is_available_returns_false_when_no_backend_installed(monkeypatch) -> None:
    """Seul le cas "un backend fonctionne" était testé jusqu'ici."""
    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", None)
    monkeypatch.setitem(sys.modules, "pytesseract", None)

    assert OCREngine().is_available() is False


# ── Sélection du backend réel ────────────────────────────────────────────
#
# Comme pour modules/stt_engine.py : _load_backend() lui-même (choix
# RapidOCR -> repli pytesseract) et les deux adaptateurs
# (_RapidOCRBackend, _TesseractBackend) n'étaient jamais exercés — tous
# les tests ci-dessus injectent un backend factice.

def test_load_backend_prefers_rapidocr(monkeypatch) -> None:
    class _FakeRapidOCR:
        pass

    monkeypatch.setitem(
        sys.modules, "rapidocr_onnxruntime", SimpleNamespace(RapidOCR=_FakeRapidOCR)
    )

    backend = OCREngine()._load_backend()

    assert isinstance(backend, _RapidOCRBackend)
    assert isinstance(backend.engine, _FakeRapidOCR)


def test_load_backend_falls_back_to_tesseract(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", None)
    monkeypatch.setitem(sys.modules, "pytesseract", SimpleNamespace(image_to_string=lambda *a, **k: ""))

    backend = OCREngine()._load_backend()

    assert isinstance(backend, _TesseractBackend)


def test_rapidocr_backend_returns_empty_result_when_nothing_detected() -> None:
    """RapidOCR renvoie None (pas une liste vide) quand rien n'est détecté."""
    class _FakeEngine:
        def __call__(self, image_path):
            return None, {"det": 0.0}

    result = _RapidOCRBackend(_FakeEngine()).extract("capture.png")

    assert result.text == ""
    assert result.lines == []
    assert result.confidence == 0.0


def test_rapidocr_backend_converts_detections_to_a_result() -> None:
    raw = [
        [[[0, 0], [10, 0], [10, 10], [0, 10]], "Error 404", 0.9],
        [[[0, 20], [10, 20], [10, 30], [0, 30]], "page introuvable", 0.7],
    ]

    class _FakeEngine:
        def __call__(self, image_path):
            return raw, {"det": 1.0}

    result = _RapidOCRBackend(_FakeEngine()).extract("capture.png")

    assert result.text == "Error 404\npage introuvable"
    assert result.lines == ["Error 404", "page introuvable"]
    assert result.confidence == pytest.approx(0.8)


def test_tesseract_backend_extracts_text_via_pytesseract(monkeypatch, tmp_path) -> None:
    import PIL.Image

    image = tmp_path / "capture.png"
    image.write_bytes(b"\x89PNG faux contenu")
    captured: dict = {}

    monkeypatch.setattr(PIL.Image, "open", lambda path: "image-ouverte")

    class _FakePytesseract:
        @staticmethod
        def image_to_string(img, lang=None):
            captured["image"] = img
            captured["lang"] = lang
            return "Error 404\n\n   \npage introuvable\n"

    result = _TesseractBackend(_FakePytesseract).extract(str(image))

    assert result.text == "Error 404\npage introuvable"
    assert result.lines == ["Error 404", "page introuvable"]
    assert result.confidence == 0.0, "Tesseract ne donne pas de score global sans image_to_data"
    assert captured["lang"] == "fra+eng", "Tesseract attend 'fra+eng', pas une liste"
    assert captured["image"] == "image-ouverte"


# ── Sécurité ──────────────────────────────────────────────────────────

def test_ocr_makes_no_outbound_call() -> None:
    """
    Le texte extrait est du verbatim d'écran — mot de passe affiché,
    relevé ouvert. Plus sensible que la description du VLM, qui
    paraphrase. Rien ne doit sortir de la machine.
    """
    from modules import ocr_engine

    source = inspect.getsource(ocr_engine)
    for forbidden in ("requests.", "urllib", "http://", "https://", "openai"):
        assert forbidden not in source


def test_no_torch_dependency() -> None:
    """
    easyocr, prévu par mission_01, tire torch et utilise le GPU — soit
    exactement ce qu'on évite en refusant internvl2 (contention avec
    Ollama, VISION_LONG_TERME §3).
    """
    from modules import ocr_engine

    source = inspect.getsource(ocr_engine)
    assert "import torch" not in source
    assert "easyocr" not in source.replace("easyocr,", "").replace(
        "easyocr (", ""
    ) or "mission_01" in source


# ── Composition du bloc vision ────────────────────────────────────────

def _block(screen_text: str, visual: str) -> str:
    from core.lucas_core import LucasCore

    return LucasCore._compose_vision_block(screen_text, visual)


def test_both_sources_are_labelled_distinctly() -> None:
    """
    Sans hiérarchie explicite, le LLM accorde la même confiance à une
    transcription exacte et à une description approximative, et invente
    un mélange des deux.
    """
    block = _block("Error 404", "un navigateur ouvert")

    assert "transcription exacte" in block
    assert "indicatif" in block
    assert block.index("Error 404") < block.index("un navigateur ouvert"), (
        "le texte exact doit précéder le contexte visuel"
    )


def test_text_only_tells_the_model_not_to_speculate() -> None:
    """
    C'est le cas NORMAL en v1.0 : le VLM est coupé (config.VLM_ENABLED),
    llava fabriquant des messages d'erreur absents de l'écran. La consigne
    ne doit donc pas annoncer une panne — le modèle se dédirait alors
    qu'il a bien le texte — mais interdire la spéculation sur ce qu'on ne
    lui donne plus : l'application et la disposition.
    """
    block = _block("Error 404", "")
    assert "Error 404" in block
    assert "texte seul" in block
    assert "spécule pas" in block


def test_visual_only_keeps_the_previous_behaviour() -> None:
    block = _block("", "un éditeur de code")
    assert "un éditeur de code" in block
    assert "transcription exacte" not in block


def test_the_anti_refusal_instruction_survives_every_combination() -> None:
    """
    C'est cette phrase qui a corrigé le refus de qwen — il répondait
    « je ne peux pas voir l'écran » alors que la description était dans
    son contexte. La perdre ferait revenir le bug.
    """
    for screen_text, visual in (("texte", "visuel"), ("texte", ""), ("", "visuel")):
        assert "Ne dis JAMAIS" in _block(screen_text, visual)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
