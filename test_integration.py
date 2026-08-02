# test_integration.py — la chaîne réelle, sans doublure
#
# Les 324 autres tests mockent tout : Ollama, Piper, DuckDuckGo, psutil.
# C'est ce qui les rend rapides et fiables, mais aucun ne prouve que les
# morceaux s'emboîtent réellement. Un changement de format de réponse
# d'Ollama, un modèle absent, une base verrouillée : rien de tout ça
# n'apparaîtrait.
#
# Ces tests-ci parlent aux vrais services. Ils sont donc :
#   • LENTS (plusieurs secondes chacun, ~25 s pour la vision à froid)
#   • dépendants de l'environnement — Ollama lancé, modèles installés
#   • exclus de la suite par défaut, via le marqueur « integration »
#
# Lancement :  just test-integration
#         ou :  pytest test_integration.py -m integration -v
#
# Chaque test se saute proprement si sa dépendance manque, plutôt que
# d'échouer : un test rouge parce qu'Ollama est éteint n'apprend rien.

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

OLLAMA_TIMEOUT = 5


def _ollama_models() -> list[str]:
    """Modèles réellement disponibles, ou liste vide si Ollama est absent."""
    try:
        import requests

        from config import OLLAMA_URL

        base = OLLAMA_URL.rsplit("/api/", 1)[0]
        response = requests.get(f"{base}/api/tags", timeout=OLLAMA_TIMEOUT)
        return [model["name"] for model in response.json().get("models", [])]
    except Exception:  # noqa: BLE001 — absence = saut, jamais échec
        return []


def _requires_model(name: str) -> None:
    models = _ollama_models()
    if not models:
        pytest.skip("Ollama ne répond pas — lancer « ollama serve »")
    if not any(m == name or m.startswith(f"{name}:") for m in models):
        pytest.skip(f"modèle « {name} » absent — ollama pull {name}")


@pytest.fixture
def temp_core():
    """LucasCore sur une base temporaire : on ne touche pas à lucas_memory.db."""
    from core.lucas_core import LucasCore
    from memory.memory_manager import MemoryManager

    core = LucasCore.__new__(LucasCore)
    core.memory = MemoryManager(db_path=Path(tempfile.mkdtemp()) / "integration.db")
    yield core
    core.close()


# ── Chaîne conversationnelle ──────────────────────────────────────────

def test_a_real_question_gets_a_real_answer(temp_core) -> None:
    """
    Routage, construction du contexte, appel au LLM, écriture en mémoire :
    tout l'enchaînement, sans une seule doublure.
    """
    from config import MODEL_NAME

    _requires_model(MODEL_NAME)

    answer = temp_core.ask("Réponds simplement « bonjour » et rien d'autre.")

    assert answer.strip(), "une réponse vide signale une rupture de la chaîne"
    assert not answer.startswith("[Erreur]"), answer
    assert len(temp_core.memory.load_history()) == 2, "question et réponse en base"


def test_the_system_prompt_reaches_the_model(temp_core) -> None:
    """
    Luca's doit se présenter sous son nom : c'est la preuve que
    SYSTEM_PROMPT arrive bien jusqu'au modèle.
    """
    from config import MODEL_NAME

    _requires_model(MODEL_NAME)

    answer = temp_core.ask("Comment t'appelles-tu ? Réponds en trois mots maximum.")
    assert "luca" in answer.lower(), f"réponse inattendue : {answer}"


def test_a_sensitive_question_stays_local(temp_core) -> None:
    """
    Garde de bout en bout sur la règle 3 : la question ne doit pas
    partir au cloud, et la réponse ne doit pas être le message du stub.
    """
    from config import MODEL_NAME
    from core.router import route

    _requires_model(MODEL_NAME)

    question = "Quel est mon budget mensuel ?"
    assert route(question) == "local"

    answer = temp_core.ask(question)
    assert "[Cloud" not in answer, "une question sensible a atteint le chemin cloud"


# ── Voix locale ───────────────────────────────────────────────────────

def test_piper_produces_real_audio(tmp_path) -> None:
    """Le TTS local doit produire un WAV lisible, pas un fichier vide."""
    import wave

    from modules.piper_engine import PiperEngine

    engine = PiperEngine()
    if not engine.is_available():
        pytest.skip("modèle Piper absent — python -m piper.download_voices")

    output = tmp_path / "voix.wav"
    engine.synthesize("Ceci est un test de la voix locale.", str(output))

    with wave.open(str(output), "rb") as wav:
        assert wav.getnframes() > 0, "fichier audio vide"
        duration = wav.getnframes() / wav.getframerate()
    assert duration > 0.5, f"durée suspecte : {duration:.2f}s"


# ── Vision ────────────────────────────────────────────────────────────

def test_the_vlm_describes_the_real_screen() -> None:
    """
    ⚠️ Lent : ~25 s au premier appel, le temps qu'Ollama charge llava en
    VRAM, puis moins d'une seconde tant que le modèle reste chaud.
    """
    from config import VLM_MODEL
    from modules.vision_manager import VisionManager

    _requires_model(VLM_MODEL)

    description = VisionManager(model=VLM_MODEL).see_and_describe()

    assert description.strip()
    assert not description.startswith("Erreur analyse"), description


# ── Mémoire partagée ──────────────────────────────────────────────────

def test_ui_and_daemon_can_write_at_the_same_time(tmp_path) -> None:
    """
    Le daemon enregistre des événements sécurité pendant que Cyril
    discute : deux connexions SQLite écrivent dans la même base. Un
    verrou mal géré se verrait ici et nulle part ailleurs.
    """
    from memory.memory_manager import MemoryManager

    path = tmp_path / "concurrent.db"
    ui = MemoryManager(db_path=path)
    daemon = MemoryManager(db_path=path)

    try:
        for i in range(50):
            ui.save_message("user", f"message {i}")
            daemon.save_event("security_test", f"événement {i}")

        assert len(ui.load_history()) == 50
        assert len(daemon.load_recent_events(limit=100)) == 50
    finally:
        ui.close()
        daemon.close()


# ── Capteurs de sécurité ──────────────────────────────────────────────

def test_security_sensors_run_on_the_real_machine() -> None:
    """
    Les capteurs sont testés avec psutil mocké. Ici ils lisent les vrais
    process, sockets et clés de registre : c'est le seul endroit où une
    erreur d'API Windows apparaîtrait.
    """
    from security import BehaviourHistory, Guardian, PersistenceWatch, PrivacyShield

    history = BehaviourHistory(Path(tempfile.mkdtemp()) / "h.json")

    findings = (
        Guardian().scan()
        + PrivacyShield(history=history).scan()
        + PersistenceWatch(history=history).scan()
    )

    kinds = {f.kind for f in findings}
    assert "autostart_inventory" in kinds, "l'inventaire de démarrage doit remonter"
    assert all(f.summary for f in findings), "un signal sans description est inutilisable"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-m", "integration", "-v"]))
