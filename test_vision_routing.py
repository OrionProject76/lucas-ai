# test_vision_routing.py — Luca's regarde l'écran, et seulement quand il faut
#
# Deux propriétés testées :
#   1. La capture ne se déclenche que sur une demande explicite — un VLM
#      coûte plusieurs secondes, le lancer à chaque message est exclu.
#   2. Une question sur l'écran est forcée en LOCAL. L'image ne part
#      jamais, mais sa description en dirait autant.
#
# Aucune capture réelle, aucun appel à Ollama : VisionManager est mocké.

from __future__ import annotations

import pytest

from core import orion_core
from core.orion_core import OrionCore
from core.router import route, should_use_vision

# Marqueur du bloc vision injecté dans le prompt. Défini une fois :
# répété en dur dans chaque test, il a divergé du code au premier
# changement de formulation.
VISION_MARKER = "TU VIENS DE REGARDER L'ÉCRAN"

# ── Déclencheur ───────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "question",
    [
        "qu'est-ce que tu vois à l'écran ?",
        "regarde mon écran",
        "c'est quoi cette erreur ?",
        "aide-moi avec cette fenêtre",
        "que vois-tu ?",
        "fais une capture d'écran",
    ],
)
def test_explicit_requests_trigger_vision(question: str) -> None:
    assert should_use_vision(question)


@pytest.mark.parametrize(
    "question",
    [
        "quelle heure il est",
        "raconte-moi une blague",
        "regarde si tu peux m'aider",
        "explique-moi les tableaux Python",
        "quel temps fait-il demain",
    ],
)
def test_ordinary_questions_do_not_trigger_vision(question: str) -> None:
    """
    Une capture + analyse VLM coûte plusieurs secondes. « regarde si tu
    peux m'aider » ne doit surtout pas la déclencher.
    """
    assert not should_use_vision(question)


# ── Routage ───────────────────────────────────────────────────────────

def test_a_screen_question_stays_local() -> None:
    """
    L'image reste sur la machine, mais « une fenêtre affichant un solde
    de 3200 € » est tout aussi révélateur. La question doit donc être
    traitée en local.
    """
    assert route("regarde mon écran et analyse cette projection") == "local"


def test_vision_beats_a_cloud_keyword() -> None:
    """« analyse » enverrait au cloud ; la vision doit l'emporter."""
    assert route("analyse ce qui est à l'écran") == "local"


# ── Injection dans le prompt ──────────────────────────────────────────

class _FakeMemory:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def load_history(self):
        return []

    def load_recent_events(self, limit=5):
        return []

    def save_event(self, event_type, details=""):
        self.events.append((event_type, details))


@pytest.fixture
def core(monkeypatch):
    monkeypatch.setattr(orion_core, "get_snapshot", dict)
    monkeypatch.setattr(
        orion_core, "format_for_prompt",
        lambda snapshot, include_window=True: "[système]",
    )
    instance = OrionCore.__new__(OrionCore)
    instance.memory = _FakeMemory()
    return instance


def _fake_vision(monkeypatch, description: str, captured: dict | None = None):
    class _FakeVisionManager:
        def __init__(self, model=None):
            self.model = model

        def capture_screen(self, output_path=None):
            return "data/screenshot.png"

        def analyze_image(self, path, prompt=None):
            if captured is not None:
                captured["prompt"] = prompt
                captured["path"] = path
            return description

        def see_and_describe(self, prompt=None):
            return description

    monkeypatch.setattr(
        "modules.vision_manager.VisionManager", _FakeVisionManager
    )


def test_screen_description_reaches_the_prompt(core, monkeypatch) -> None:
    _fake_vision(monkeypatch, "un éditeur de code affichant du Python")
    messages = core._build_messages("qu'est-ce que tu vois à l'écran ?", "local")
    assert any("éditeur de code" in m["content"] for m in messages)


def test_no_capture_without_an_explicit_request(core, monkeypatch) -> None:
    """Le VLM ne doit pas être sollicité pour une question ordinaire."""
    def must_not_be_called(model=None):
        raise AssertionError("aucune capture ne doit être déclenchée")

    monkeypatch.setattr("modules.vision_manager.VisionManager", must_not_be_called)
    core._build_messages("quelle heure il est", "local")


def test_no_capture_on_a_cloud_request(core, monkeypatch) -> None:
    """Garde redondante : même si route() se trompait, rien ne part."""
    def must_not_be_called(model=None):
        raise AssertionError("pas de vision sur un chemin cloud")

    monkeypatch.setattr("modules.vision_manager.VisionManager", must_not_be_called)
    messages = core._build_messages("regarde mon écran", "cloud")
    assert not any(VISION_MARKER in m["content"] for m in messages)


def test_vision_can_be_disabled(core, monkeypatch) -> None:
    monkeypatch.setattr(orion_core, "VISION_ENABLED", False)

    def must_not_be_called(model=None):
        raise AssertionError("VISION_ENABLED=False doit tout couper")

    monkeypatch.setattr("modules.vision_manager.VisionManager", must_not_be_called)
    core._build_messages("regarde mon écran", "local")


def test_vision_use_is_logged(core, monkeypatch) -> None:
    _fake_vision(monkeypatch, "un bureau")
    core._build_messages("regarde mon écran", "local")
    assert "vision_used" in [t for t, _ in core.memory.events]


# ── Le VLM reçoit la vraie question ───────────────────────────────────

def test_the_users_question_reaches_the_vlm(core, monkeypatch) -> None:
    """
    « C'est quoi cette erreur ? » doit être posée au modèle vision.
    Une description passe-partout obligerait le LLM principal à deviner
    ce qui compte dans un écran entier, et perdrait le détail demandé.
    """
    captured: dict = {}
    _fake_vision(monkeypatch, "une erreur de chemin invalide", captured)

    core._build_messages("c'est quoi cette erreur à l'écran ?", "local")

    assert "c'est quoi cette erreur" in captured["prompt"]


def test_vision_prompt_asks_for_french() -> None:
    """llava bascule spontanément en anglais sans consigne explicite."""
    prompt = OrionCore._vision_prompt("que vois-tu ?")
    assert "français" in prompt
    assert "capture" in prompt.lower()
    assert "que vois-tu ?" in prompt


def test_vision_prompt_demands_concrete_detail() -> None:
    """
    Sans consigne, llava rend une paraphrase vague (« un message d'erreur
    ou de confirmation ») au lieu de citer ce qui est écrit.
    """
    prompt = OrionCore._vision_prompt("c'est quoi cette erreur ?").lower()
    assert "concrètement" in prompt
    assert "cite" in prompt


def test_injected_block_forbids_denying_sight(core, monkeypatch) -> None:
    """
    Le bug le plus sournois de la vision : qwen répondait « je ne peux
    pas voir l'écran » alors que la description était juste au-dessus
    dans son contexte. Un modèle de texte affirme par défaut qu'il n'a
    pas d'yeux — le bloc doit le contredire explicitement.
    """
    _fake_vision(monkeypatch, "une fenêtre de console")
    messages = core._build_messages("que vois-tu à l'écran ?", "local")
    block = next(m["content"] for m in messages if VISION_MARKER in m["content"])

    assert "Ne dis JAMAIS que tu ne peux pas voir" in block
    assert "une fenêtre de console" in block


def test_injected_block_is_an_instruction_not_a_statement(core, monkeypatch) -> None:
    """Rédigé comme un simple constat, le bloc était ignoré."""
    _fake_vision(monkeypatch, "un éditeur")
    messages = core._build_messages("regarde mon écran", "local")
    block = next(m["content"] for m in messages if VISION_MARKER in m["content"])

    assert "Appuie-toi d'abord" in block, "le bloc doit donner un ordre"


# ── Vision hybride : OCR + VLM ────────────────────────────────────────

def _fake_ocr(monkeypatch, text: str, raises=None):
    """Remplace le moteur OCR sans toucher au disque."""
    from modules.ocr_engine import OCRResult

    class _FakeOCREngine:
        def extract_text(self, path):
            if raises:
                raise raises
            return OCRResult(text=text, lines=text.splitlines())

    monkeypatch.setattr("modules.ocr_engine.OCREngine", _FakeOCREngine)


def test_ocr_text_reaches_the_prompt(core, monkeypatch) -> None:
    _fake_vision(monkeypatch, "un terminal")
    _fake_ocr(monkeypatch, "FileNotFoundError: config.json")

    messages = core._build_messages("c'est quoi cette erreur à l'écran ?", "local")
    block = next(m["content"] for m in messages if VISION_MARKER in m["content"])

    assert "FileNotFoundError: config.json" in block
    assert "un terminal" in block


def test_ocr_failure_leaves_the_vlm_alone(core, monkeypatch) -> None:
    """Comportement d'avant l'OCR : la vision doit rester utilisable."""
    _fake_vision(monkeypatch, "un éditeur de code")
    _fake_ocr(monkeypatch, "", raises=RuntimeError("moteur absent"))

    messages = core._build_messages("regarde mon écran", "local")
    block = next(m["content"] for m in messages if VISION_MARKER in m["content"])

    assert "un éditeur de code" in block
    assert "ocr_failed" in [t for t, _ in core.memory.events]


def test_vlm_failure_leaves_the_ocr_alone(core, monkeypatch) -> None:
    _fake_vision(monkeypatch, "Erreur analyse (modèle absent)")
    _fake_ocr(monkeypatch, "Solde : 3200 euros")

    messages = core._build_messages("regarde mon écran", "local")
    block = next(m["content"] for m in messages if VISION_MARKER in m["content"])

    assert "Solde : 3200 euros" in block
    assert "contexte visuel n'a pas pu" in block


def test_both_failing_produces_no_block(core, monkeypatch) -> None:
    _fake_vision(monkeypatch, "Erreur analyse")
    _fake_ocr(monkeypatch, "", raises=RuntimeError("absent"))

    messages = core._build_messages("regarde mon écran", "local")

    assert not any(VISION_MARKER in m["content"] for m in messages)
    assert "vision_failed" in [t for t, _ in core.memory.events]


def test_long_screen_text_is_truncated(core, monkeypatch) -> None:
    """
    Un écran 4K produit des milliers de caractères. Sans borne, le texte
    de l'écran noierait l'historique et le prompt système.
    """
    from config import OCR_MAX_CHARS

    _fake_vision(monkeypatch, "un terminal")
    # Caractère absent du texte d'instruction, sinon le compte inclut
    # les « x » de « exact » et le test ment.
    _fake_ocr(monkeypatch, "ZZ" * OCR_MAX_CHARS)

    messages = core._build_messages("regarde mon écran", "local")
    block = next(m["content"] for m in messages if VISION_MARKER in m["content"])

    assert block.count("Z") <= OCR_MAX_CHARS


def test_screen_text_is_never_logged(core, monkeypatch) -> None:
    """
    Le texte OCR est du verbatim d'écran. La table d'événements ne doit
    pas en devenir une copie — on journalise l'usage, jamais le contenu.
    """
    secret = "IBAN FR76 3000 4000 0512 3456 7890"
    _fake_vision(monkeypatch, "un navigateur")
    _fake_ocr(monkeypatch, secret)

    core._build_messages("regarde mon écran", "local")

    for _event_type, details in core.memory.events:
        assert secret not in details


def test_ocr_can_be_disabled(core, monkeypatch) -> None:
    monkeypatch.setattr(orion_core, "OCR_ENABLED", False)
    _fake_vision(monkeypatch, "un terminal")

    def must_not_be_called():
        raise AssertionError("OCR_ENABLED=False doit couper l'OCR")

    monkeypatch.setattr("modules.ocr_engine.OCREngine", must_not_be_called)

    messages = core._build_messages("regarde mon écran", "local")
    block = next(m["content"] for m in messages if VISION_MARKER in m["content"])
    assert "un terminal" in block


def test_the_screen_is_captured_only_once(core, monkeypatch) -> None:
    """
    Recapturer entre l'OCR et le VLM donnerait deux écrans différents si
    Cyril change de fenêtre entre-temps.
    """
    captures: list[str] = []

    class _CountingVisionManager:
        def __init__(self, model=None):
            pass

        def capture_screen(self, output_path=None):
            captures.append("capture")
            return "data/screenshot.png"

        def analyze_image(self, path, prompt=None):
            return "un terminal"

    monkeypatch.setattr("modules.vision_manager.VisionManager", _CountingVisionManager)
    _fake_ocr(monkeypatch, "du texte")

    core._build_messages("regarde mon écran", "local")
    assert len(captures) == 1


# ── Dégradation ───────────────────────────────────────────────────────

def test_vlm_failure_does_not_block_the_answer(core, monkeypatch) -> None:
    """
    Une vision indisponible doit dégrader la réponse, pas empêcher
    Luca's de répondre.

    Depuis l'arrivée de l'OCR, un VLM en panne ne supprime plus le bloc :
    le texte lu à l'écran suffit. Il faut donc couper les DEUX sources
    pour retrouver l'absence de bloc — c'est ce que vérifie
    test_both_failing_produces_no_block.
    """
    _fake_vision(monkeypatch, "Erreur analyse (modèle llava peut-être non installé)")
    _fake_ocr(monkeypatch, "", raises=RuntimeError("moteur absent"))

    messages = core._build_messages("regarde mon écran", "local")

    assert not any(VISION_MARKER in m["content"] for m in messages)
    assert messages, "le prompt doit rester exploitable"
    assert "vision_failed" in [t for t, _ in core.memory.events]


def test_vlm_exception_is_caught(core, monkeypatch) -> None:
    class _Broken:
        def __init__(self, model=None):
            raise ConnectionError("Ollama injoignable")

    monkeypatch.setattr("modules.vision_manager.VisionManager", _Broken)
    messages = core._build_messages("regarde mon écran", "local")

    assert messages
    assert "vision_failed" in [t for t, _ in core.memory.events]


def test_empty_description_is_not_injected(core, monkeypatch) -> None:
    _fake_vision(monkeypatch, "")
    messages = core._build_messages("regarde mon écran", "local")
    assert all(m["content"].strip() for m in messages)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
