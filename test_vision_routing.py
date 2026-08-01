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
    """
    ⚠️ `history` est un paramètre depuis le 01/08/2026, et il ne doit
    plus jamais redevenir une constante vide.

    Cette classe rendait `[]` en dur. Tous les tests vision tournaient
    donc sur une conversation neuve, où le bloc vision se retrouvait
    mécaniquement collé à la question — et passaient. En usage réel, avec
    90 messages accumulés, le bloc arrivait en 4e position sur 91 et le
    modèle répondait à une vieille question de l'historique.

    Quatre campagnes de tests ont validé une application cassée à cause
    de ce seul `return []`.
    """

    def __init__(self, history=None) -> None:
        self.events: list[tuple[str, str]] = []
        self._history = list(history or [])

    def load_history(self):
        return list(self._history)

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
    """
    Installe un faux VLM — et l'ACTIVE.

    Le VLM est coupé par défaut en v1.0 (config.VLM_ENABLED, llava
    fabrique). Mais un test qui prend la peine d'installer une fausse
    description veut manifestement que ce chemin s'exécute : ces tests
    décrivent le comportement à retrouver en v1.1 avec internvl2, et ils
    doivent continuer à tourner d'ici là, sinon la réactivation se fera
    sans filet.

    La garantie que le VLM est bien coupé en production ne repose donc
    pas sur ces tests, mais sur test_the_vlm_is_off_in_v1_and_never_called,
    qui vérifie le réglage réel de config.py.
    """
    monkeypatch.setattr(orion_core, "VLM_ENABLED", True)

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
    # La consigne dit au modèle de s'en tenir au texte, sans annoncer une
    # panne : c'est le cas normal en v1.0, VLM coupé (config.VLM_ENABLED).
    assert "texte seul" in block
    assert "spécule pas" in block


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


# ── Position dans le prompt, avec un historique réel ──────────────────
#
# Le bug qui a résisté à quatre campagnes de tests. Tout le reste
# fonctionnait — déclencheur, OCR, VLM, construction du bloc — mais le
# bloc était injecté AVANT l'historique. Sur une base neuve ça ne se
# voyait pas ; avec 90 messages accumulés, l'observation de l'écran
# devenait du contexte ancien et le modèle répondait à côté.

def _long_history(turns: int = 45):
    """Une conversation déjà bien remplie, comme celle de Cyril."""
    history = []
    for i in range(turns):
        history.append(("user", f"vieille question numéro {i}"))
        history.append(("assistant", f"vieille réponse numéro {i}"))
    return history


@pytest.fixture
def core_with_history(monkeypatch):
    monkeypatch.setattr(orion_core, "get_snapshot", dict)
    monkeypatch.setattr(
        orion_core, "format_for_prompt",
        lambda snapshot, include_window=True: "[système]",
    )
    instance = OrionCore.__new__(OrionCore)
    instance.memory = _FakeMemory(
        history=_long_history() + [("user", "c'est écrit quoi ?")]
    )
    return instance


def test_vision_block_sits_just_before_the_question(core_with_history, monkeypatch):
    """
    LE test qui manquait. L'observation de l'écran doit être le dernier
    contexte que le modèle lise avant la question — pas le premier.
    """
    _fake_vision(monkeypatch, "un éditeur de texte")
    messages = core_with_history._build_messages("c'est écrit quoi ?", "local")

    positions = [i for i, m in enumerate(messages) if VISION_MARKER in m["content"]]
    assert positions, "le bloc vision doit être présent"

    vision_at = positions[0]
    assert messages[-1]["content"] == "c'est écrit quoi ?", (
        "la question courante doit rester le dernier message"
    )
    assert vision_at == len(messages) - 2, (
        f"bloc vision en position {vision_at} sur {len(messages)} — il doit être "
        "immédiatement avant la question, sinon l'historique le noie"
    )


def test_history_comes_before_the_observation(core_with_history, monkeypatch):
    """
    L'ordre inverse est celui qui a cassé l'application : 4 messages
    système dont la vision, puis 87 messages d'historique par-dessus.
    """
    _fake_vision(monkeypatch, "un éditeur de texte")
    messages = core_with_history._build_messages("c'est écrit quoi ?", "local")

    vision_at = next(i for i, m in enumerate(messages) if VISION_MARKER in m["content"])
    last_old = max(
        i for i, m in enumerate(messages)
        if m["content"].startswith(("vieille question", "vieille réponse"))
    )
    assert last_old < vision_at, (
        "tout l'historique doit précéder l'observation de l'écran"
    )


def test_the_current_question_is_not_duplicated(core_with_history, monkeypatch):
    """
    La question est isolée de l'historique pour glisser l'observation
    avant elle. Elle ne doit pas pour autant apparaître deux fois.
    """
    _fake_vision(monkeypatch, "un éditeur de texte")
    messages = core_with_history._build_messages("c'est écrit quoi ?", "local")

    assert sum(m["content"] == "c'est écrit quoi ?" for m in messages) == 1


def test_the_question_is_kept_when_vision_is_off(core_with_history, monkeypatch):
    """
    L'isolement de la question ne doit pas la faire disparaître quand
    aucun bloc n'est injecté — c'est le cas de la grande majorité des
    messages.
    """
    messages = core_with_history._build_messages("quelle heure il est", "local")
    assert messages[-1]["content"] == "c'est écrit quoi ?"


def test_history_is_shortened_when_vision_fires(core_with_history, monkeypatch):
    """
    La seconde moitié du bug. Le bloc bien placé ne suffisait pas : avec
    100 messages d'historique — dont douze réponses « pourriez-vous me
    donner plus de contexte » — le modèle imitait sa propre mauvaise
    habitude. Mesuré 0/9 à 100 messages, 9/9 à 6.
    """
    from config import SOURCE_HISTORY_MESSAGES

    _fake_vision(monkeypatch, "un éditeur de texte")
    messages = core_with_history._build_messages("c'est écrit quoi ?", "local")

    old = [m for m in messages if m["content"].startswith(("vieille question", "vieille réponse"))]
    assert len(old) <= SOURCE_HISTORY_MESSAGES, (
        f"{len(old)} messages d'historique joints alors que la vision est "
        f"active — au-delà de {SOURCE_HISTORY_MESSAGES}, l'observation est noyée"
    )


def test_history_is_shortened_when_the_rag_fires(core_with_history, monkeypatch):
    """
    ⚠️ CE TEST MANQUAIT, et c'est pour ça que le RAG est resté cassé
    après la correction de la vision : le plafond ne s'appliquait qu'à
    l'écran. En conditions réelles, « Résume-moi mon CV » recevait ses
    extraits sous 70 messages d'historique, et Luca's demandait à Cyril
    de lui dicter son CV — alors que le bloc était juste au-dessus.

    Toute source externe ajoutée au prompt doit passer par ce plafond.
    """
    from config import SOURCE_HISTORY_MESSAGES

    monkeypatch.setattr(
        orion_core, "should_use_rag", lambda text: True
    )

    class _FakeRAG:
        def get_context(self, query, top_k=3):
            return "Contexte trouvé dans les documents:\n[Extrait 1] Aide-soignant"

    monkeypatch.setattr(orion_core, "RAGManager", _FakeRAG)

    messages = core_with_history._build_messages("résume-moi mon CV", "local")

    old = [m for m in messages if m["content"].startswith(("vieille question", "vieille réponse"))]
    assert len(old) <= SOURCE_HISTORY_MESSAGES, (
        f"{len(old)} messages d'historique joints alors que le RAG est "
        f"actif — au-delà de {SOURCE_HISTORY_MESSAGES}, les extraits sont noyés"
    )
    assert "Aide-soignant" in messages[-2]["content"], (
        "le bloc RAG doit être immédiatement avant la question"
    )


def test_history_is_kept_whole_without_vision(core_with_history):
    """
    Le raccourcissement ne vaut QUE pour la vision. Une conversation
    ordinaire garde sa mémoire longue — c'est tout l'intérêt du projet.
    """
    messages = core_with_history._build_messages("quelle heure il est", "local")

    old = [m for m in messages if m["content"].startswith(("vieille question", "vieille réponse"))]
    assert len(old) == 90, f"historique tronqué à {len(old)} sans raison"


def test_the_vlm_is_off_in_v1_and_never_called(core_with_history, monkeypatch):
    """
    llava fabrique : quatre observations réelles sur quatre, dont un
    traceback Python complet pour un bug inexistant. Coupé en v1.0.

    ⚠️ Ce test ne consacre PAS l'abandon de la description visuelle : il
    consacre le fait que le VLM ne doit pas tourner tant que le modèle
    reste llava. En v1.1, avec internvl2, VLM_ENABLED repasse à True et
    ce test devient à mettre à jour, pas à supprimer.
    """
    from config import VLM_ENABLED

    assert VLM_ENABLED is False, (
        "VLM_ENABLED est repassé à True — vérifier que le modèle n'est "
        "plus llava (voir config.py) avant de modifier ce test"
    )

    appels = []

    class _VLMQuiNeDoitPasTourner:
        def __init__(self, model=None):
            pass

        def capture_screen(self, output_path=None):
            return "data/screenshot.png"

        def analyze_image(self, path, prompt=None):
            appels.append(prompt)
            return "description fabriquée"

    monkeypatch.setattr("modules.vision_manager.VisionManager", _VLMQuiNeDoitPasTourner)
    _fake_ocr(monkeypatch, "ERREUR 0x8007007E")

    messages = core_with_history._build_messages("c'est écrit quoi ?", "local")

    assert not appels, "le VLM a été interrogé alors qu'il est désactivé"
    block = next(m for m in messages if VISION_MARKER in m["content"])
    assert "ERREUR 0x8007007E" in block["content"], "l'OCR doit rester la source"
    assert "fabriquée" not in block["content"]


def test_the_vlm_description_is_capped(core_with_history, monkeypatch):
    """
    Mesuré en usage réel : llava a rendu 10 270 caractères pour 1 761
    caractères réellement lus à l'écran. L'OCR était borné, pas lui.
    """
    from config import VLM_MAX_CHARS

    # Le plafond concerne la v1.1 : il doit rester correct le jour où le
    # VLM est réactivé avec internvl2, sinon on retrouvera les 10 270
    # caractères au premier changement de modèle.
    monkeypatch.setattr(orion_core, "VLM_ENABLED", True)
    _fake_vision(monkeypatch, "bla " * 5000)
    messages = core_with_history._build_messages("c'est écrit quoi ?", "local")

    block = next(m for m in messages if VISION_MARKER in m["content"])
    assert block["content"].count("bla") <= VLM_MAX_CHARS


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
