# test_couverture_residuelle.py — les 55 dernières lignes non couvertes
#
# ⚠️ Pourquoi ce fichier existe (06/08/2026)
# ------------------------------------------
# À la fin du chantier `ui/`, le projet était à 98 % : 55 lignes réparties
# sur 16 fichiers. Cyril a demandé de les couvrir.
#
# Elles se rangeaient en quatre familles, et l'intérêt n'est pas le même :
#
#   1. REPLIS D'ENVIRONNEMENT (ImportError, exécution en script) — ne se
#      produisent que sur une machine autrement configurée. Les couvrir
#      vérifie que Luca's DÉGRADE au lieu de tomber.
#   2. GARDES DE SÉCURITÉ (privacy_shield, guardian) — les branches qui
#      REFUSENT de signaler. Un capteur qui crie sur tout ne sera jamais
#      lu ; ces filtres sont ce qui le rend crédible.
#   3. MESSAGES D'ERREUR — chacun dit à Cyril ce qui s'est passé. Muets,
#      ils redeviendraient le silence que ce projet traque partout.
#   4. EFFETS EXTERNES (edge_tts, pygame, classifieur) — jamais appelés en
#      vrai ici : des doubles, sinon la suite dépendrait du réseau, d'une
#      carte son et d'Ollama vivant.

from __future__ import annotations

import pytest

# ⚠️ Capture de la VRAIE fonction AVANT que la fixture autouse de
# conftest.py ne la remplace. Les fixtures s'installent au démarrage de
# chaque test ; cet import, lui, a lieu à la collecte. C'est le seul
# moyen d'exercer le vrai code d'appel au classifieur, que le stub
# global rend sinon inatteignable.
from core.intent import _ask_classifier as _ask_classifier_reel

# ══ 1. Replis d'environnement ═════════════════════════════════════════

def _recharge_sans(module_cible: str, module_neutralise: str, *attributs: str) -> dict:
    """Recharge `module_cible` en rendant `module_neutralise` inimportable.

    `sys.modules[nom] = None` fait lever ImportError à l'import — mécanisme
    documenté de CPython.

    ⚠️ Rend un DICTIONNAIRE, jamais le module : `importlib.reload()` mute
    l'objet EN PLACE, donc la restauration écraserait ce qu'on veut lire.
    Piège rencontré en écrivant test_main_window_paths.py le même jour.
    """
    import importlib
    import sys

    cible = importlib.import_module(module_cible)
    ancien = sys.modules.get(module_neutralise)
    sys.modules[module_neutralise] = None  # type: ignore[assignment]
    try:
        recharge = importlib.reload(cible)
        return {nom: getattr(recharge, nom, "__absent__") for nom in attributs}
    finally:
        if ancien is None:
            sys.modules.pop(module_neutralise, None)
        else:
            sys.modules[module_neutralise] = ancien
        importlib.reload(cible)


def test_vision_manager_stays_importable_without_ollama() -> None:
    """
    Sans le paquet `ollama`, le module doit rester IMPORTABLE : la capture
    d'écran et l'OCR n'en dépendent pas, seul le VLM en a besoin. Échouer
    à l'import priverait Luca's de la vision entière pour une dépendance
    qui ne sert qu'à une partie.
    """
    valeurs = _recharge_sans("modules.vision_manager", "ollama", "ollama")
    assert valeurs["ollama"] is None


def test_rag_manager_falls_back_to_the_old_chromadb_import() -> None:
    """
    ChromaDB a déplacé ses types entre versions. Le repli sur l'ancien
    chemin d'import doit fonctionner, sinon une version antérieure
    installée sur la machine de Cyril casserait tout le RAG.
    """
    valeurs = _recharge_sans(
        "modules.rag_manager", "chromadb.api.types", "EmbeddingFunction"
    )
    assert valeurs["EmbeddingFunction"] != "__absent__", (
        "le repli doit fournir EmbeddingFunction malgré l'import moderne indisponible"
    )


def test_index_documents_adds_the_project_root_when_run_as_a_script() -> None:
    """
    `python memory/index_documents.py` depuis n'importe quel dossier doit
    marcher : sans l'insertion de la racine dans sys.path, les imports
    `config` / `modules.*` echouent.

    ⚠️ Le fichier est charge HORS PAQUET (spec_from_file_location sans
    parent), ce qui met `__package__` a "" — exactement l'etat d'une
    execution directe. Un `importlib.reload()` ne suffirait pas : il
    recalcule `__package__` a "memory" et la garde ne se declenche jamais.
    """
    import importlib.util
    import sys
    from pathlib import Path

    chemin = Path("C:/OrionAI/memory/index_documents.py")
    racine = str(chemin.resolve().parent.parent)

    chemins = list(sys.path)
    try:
        while racine in sys.path:
            sys.path.remove(racine)

        spec = importlib.util.spec_from_file_location("index_documents_script", chemin)
        # L'assertion n'est pas cosmetique : sans elle, un chemin devenu
        # faux produirait un AttributeError sur None au lieu de dire que
        # le fichier est introuvable.
        assert spec is not None and spec.loader is not None, f"introuvable : {chemin}"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert racine in sys.path, "la racine du projet doit etre ajoutee a sys.path"
    finally:
        sys.path[:] = chemins


# ══ 2. Gardes de sécurité — les branches qui REFUSENT de signaler ══════

def test_a_finding_of_level_info_is_never_logged() -> None:
    """
    Guardian ne journalise que le non-trivial. Sans ce filtre, la table
    d'événements se remplirait de bruit et le panneau de sécurité
    deviendrait illisible — un capteur qu'on n'ouvre plus ne protège rien.
    """
    from conftest import event_recorder
    from security.guardian import Guardian
    from security.types import INFO, WARNING, Finding

    events, log_event = event_recorder()
    guardian = Guardian(log_event=log_event)

    guardian._log([
        Finding(severity=INFO, kind="rien_de_grave", summary="anodin", evidence={}),
        Finding(severity=WARNING, kind="a_signaler", summary="suspect", evidence={}),
    ])

    types = [t for t, _ in events]
    assert "security_rien_de_grave" not in types, "un signal INFO ne doit pas être journalisé"
    assert "security_a_signaler" in types


def test_a_process_without_an_executable_path_is_not_flagged() -> None:
    """
    Sans chemin d'exécutable, on ne peut PAS dire si le binaire vient d'un
    répertoire temporaire. Signaler quand même produirait un faux positif
    sur des processus système, dont le chemin est souvent inaccessible.
    """
    from security.privacy_shield import PrivacyShield

    assert PrivacyShield._check_volatile_process_online("x.exe", "", "1.2.3.4:443") is None


def test_a_service_bound_to_localhost_is_not_a_wide_open_listener() -> None:
    """
    Écouter sur 127.0.0.1 n'expose rien au réseau. C'est le cas de la
    majorité des services d'une machine : sans ce filtre, le capteur
    remonterait des dizaines de signaux sans intérêt.
    """
    from security.privacy_shield import PrivacyShield

    class _Adresse:
        ip = "127.0.0.1"
        port = 9999

    # 3e parametre = le CHEMIN de l'executable. J'y passais "1234" en le
    # prenant pour un PID — sans effet sur ce test, qui sort avant, mais
    # un lecteur en aurait tire une fausse idee de la signature.
    assert PrivacyShield._check_wide_open_listener("app.exe", _Adresse(), "") is None


# ══ 3. Messages d'erreur — le contraire du silence ════════════════════

def test_a_model_that_reasons_without_concluding_says_so(monkeypatch) -> None:
    """
    Mesuré 2 fois sur 16 avec gpt-oss:20b : `content` vide, tout le texte
    dans `thinking`. Rendre "" serait indiscernable d'une panne côté
    Cyril — le message doit le dire.
    """
    from core import local_llm

    class _Reponse:
        status_code = 200

        def json(self):
            return {"message": {"content": "", "thinking": "je réfléchis"}}

        def raise_for_status(self):
            pass

    monkeypatch.setattr(local_llm, "post_chat", lambda url, payload, timeout=None: _Reponse())
    monkeypatch.setattr(local_llm, "extract_reply", lambda message: "")

    reponse = local_llm.ask_local([{"role": "user", "content": "salut"}])
    assert "sans produire de réponse exploitable" in reponse


def test_the_cloud_says_it_is_not_configured_rather_than_failing(monkeypatch) -> None:
    """Sans clé, le message doit expliquer QUOI faire, pas planter."""
    from core import cloud_llm

    monkeypatch.setattr(cloud_llm, "ANTHROPIC_API_KEY", "")
    reponse = cloud_llm.ask_cloud([{"role": "user", "content": "salut"}])
    assert "non configuré" in reponse.lower()
    assert "set_anthropic_key" in reponse


def test_the_cloud_with_a_key_calls_anthropic_and_returns_the_text(monkeypatch, tmp_path) -> None:
    """
    Avec une clé, un vrai appel Anthropic est tenté — mocké ici, pas
    réseau réel (voir test_cloud_llm.py pour la couverture complète de
    core/cloud_llm.py, ce test-ci ne fait que garder la présence d'une clé
    sous surveillance de mutation).
    """
    import anthropic

    from core import cloud_llm

    monkeypatch.setattr(cloud_llm, "ANTHROPIC_API_KEY", "sk-ant-factice")
    monkeypatch.setattr(
        "memory.memory_manager.DB_PATH", tmp_path / "test_cloud_usage.db"
    )

    class _FakeTextBlock:
        type = "text"
        text = "réponse factice"

    class _FakeUsage:
        input_tokens = 10
        output_tokens = 5

    class _FakeResponse:
        def __init__(self):
            self.stop_reason = "end_turn"
            self.content = [_FakeTextBlock()]
            self.usage = _FakeUsage()

    class _FakeMessages:
        def create(self, **kwargs):
            return _FakeResponse()

    class _FakeClient:
        def __init__(self, api_key):
            self.messages = _FakeMessages()

    monkeypatch.setattr(anthropic, "Anthropic", _FakeClient)

    reponse = cloud_llm.ask_cloud([{"role": "user", "content": "salut"}])
    assert reponse == "réponse factice"


# ══ 4. Routage et extraction ══════════════════════════════════════════

def test_cloud_availability_is_read_at_each_call_not_frozen(monkeypatch) -> None:
    """
    ⚠️ La clé est relue à CHAQUE appel, délibérément : Cyril peut la
    renseigner dans `.env` sans redémarrer. Figée au démarrage, le réglage
    semblerait n'avoir aucun effet.
    """
    import config
    from core.router import cloud_is_available

    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    assert cloud_is_available() is False

    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-ant-factice")
    assert cloud_is_available() is True, "la clé doit être relue, pas mémorisée"


def test_a_single_number_is_not_an_expression() -> None:
    """
    « calcule 42 » ne contient pas de calcul. Extraire quand même
    ferait afficher « CALCUL RÉEL EFFECTUÉ : 42 = 42 » — du bruit qui
    donnerait l'impression que Luca's a travaillé.
    """
    from core.router import extract_calculation

    assert extract_calculation("combien fait 42 + ?") is None


def test_an_unreadable_foreground_process_degrades_to_empty(monkeypatch) -> None:
    """
    Le World Model ne doit JAMAIS faire tomber son appelant : une info
    manquante vaut mieux qu'une exception au milieu d'une réponse.
    """
    import core.world_model as wm

    monkeypatch.setitem(__import__("sys").modules, "win32gui", None)
    assert wm._get_active_process_name() == ""


# ══ 5. Le classifieur d'intention, vraiment appelé ════════════════════

def test_the_classifier_reads_the_label_from_the_model(monkeypatch) -> None:
    """
    ⚠️ `conftest.py` neutralise globalement `_ask_classifier` pour que la
    suite ne dépende pas d'Ollama vivant. Ce test contourne ce stub à son
    niveau — il remplace le TRANSPORT (`post_chat`), pas le classifieur —
    et exerce donc le vrai code d'appel, qui n'était jamais couvert.
    """
    from core import intent, ollama_client

    intent._CACHE.clear()
    monkeypatch.setattr(
        ollama_client, "post_chat",
        lambda url, payload, timeout=None: _ReponseClassifieur("ECRAN"),
    )
    try:
        assert _ask_classifier_reel("qu'est-ce qui est affiché ?") == "ECRAN"
    finally:
        intent._CACHE.clear()


def test_an_unreachable_classifier_degrades_instead_of_raising(monkeypatch) -> None:
    """Un classifieur indisponible dégrade le déclenchement, jamais la réponse."""
    from core import intent, ollama_client

    def _explose(url, payload, timeout=None):
        raise ConnectionError("Ollama éteint")

    intent._CACHE.clear()
    monkeypatch.setattr(ollama_client, "post_chat", _explose)
    try:
        assert _ask_classifier_reel("peu importe") is None
    finally:
        intent._CACHE.clear()


class _ReponseClassifieur:
    def __init__(self, label: str) -> None:
        self._label = label

    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return {"message": {"content": self._label}}


# ══ 6. Voix — doubles, jamais le vrai réseau ni la vraie carte son ════

def test_edge_synthesis_writes_where_it_is_told(monkeypatch, tmp_path) -> None:
    """
    ⚠️ `edge_tts` part sur le RÉSEAU (serveurs Microsoft). Le double
    évite que la suite en dépende — et qu'elle envoie du texte dehors à
    chaque exécution.
    """
    from modules import voice_manager as vm

    sauvegardes: list[str] = []

    class _FauxCommunicate:
        def __init__(self, text, voice):
            self.text = text

        async def save(self, chemin):
            sauvegardes.append(chemin)

    monkeypatch.setattr(vm.edge_tts, "Communicate", _FauxCommunicate)

    manager = vm.VoiceManager()
    cible = str(tmp_path / "sortie.mp3")
    assert manager.synthesize("bonjour", cible) == cible
    assert sauvegardes == [cible]


def test_playing_audio_reports_success(monkeypatch, tmp_path) -> None:
    """
    Double complet de pygame : jouer un vrai son rendrait la suite
    dépendante d'une carte audio, et ferait du bruit à chaque exécution.
    """
    import sys
    import types

    from modules.voice_manager import VoiceManager

    appels: list[str] = []
    faux = types.ModuleType("pygame")
    occupe = {"valeur": True}

    class _Music:
        @staticmethod
        def load(chemin):
            appels.append(f"load:{chemin}")

        @staticmethod
        def play():
            appels.append("play")

        @staticmethod
        def get_busy():
            # Occupé une seule fois : sinon la boucle d'attente est infinie.
            if occupe["valeur"]:
                occupe["valeur"] = False
                return True
            return False

    class _Mixer:
        music = _Music

        @staticmethod
        def get_init():
            return None  # force l'initialisation, la ligne à couvrir

        @staticmethod
        def init():
            appels.append("init")

    class _Clock:
        def tick(self, fps):
            appels.append("tick")

    faux.mixer = _Mixer  # type: ignore[attr-defined]
    faux.time = types.SimpleNamespace(Clock=_Clock)  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "pygame", faux)

    fichier = tmp_path / "son.mp3"
    fichier.write_bytes(b"x")
    assert VoiceManager().play_audio(str(fichier)) is True
    assert "init" in appels and "play" in appels


# ══ 7. Worker LLM (Qt) — aucun thread réel démarré ════════════════════

def test_a_stream_without_content_reports_a_readable_error(monkeypatch) -> None:
    """
    Flux vide = panne muette côté Cyril. Le worker doit émettre une
    erreur lisible plutôt que « terminer » sur rien.
    """
    pytest.importorskip("PySide6")
    from core import llm_worker as lw

    class _Flux:
        status_code = 200

        def raise_for_status(self):
            pass

        def iter_lines(self):
            yield b'{"message": {"thinking": "je reflechis"}, "done": true}'

    monkeypatch.setattr(lw, "post_chat", lambda *a, **k: _Flux())

    worker = lw.LLMWorker([{"role": "user", "content": "salut"}])
    erreurs: list[str] = []
    worker.error_occurred.connect(erreurs.append)
    worker.run()

    assert erreurs and "sans produire de réponse exploitable" in erreurs[0]


def test_a_network_problem_is_named_not_swallowed(monkeypatch) -> None:
    pytest.importorskip("PySide6")
    import requests

    from core import llm_worker as lw

    def _explose(*a, **k):
        raise requests.exceptions.RequestException("câble débranché")

    monkeypatch.setattr(lw, "post_chat", _explose)

    worker = lw.LLMWorker([{"role": "user", "content": "salut"}])
    erreurs: list[str] = []
    worker.error_occurred.connect(erreurs.append)
    worker.run()

    assert erreurs and "réseau" in erreurs[0].lower()


def test_stopping_the_worker_clears_its_running_flag() -> None:
    """`stop()` doit couper la boucle de streaming, pas seulement attendre."""
    pytest.importorskip("PySide6")
    from core.llm_worker import LLMWorker

    worker = LLMWorker([{"role": "user", "content": "salut"}])
    worker.stop()
    assert worker._is_running is False


# ══ 8. Protocole du pont mobile ═══════════════════════════════════════

@pytest.mark.parametrize("lecteur", ["read_user_audio", "read_user_image"])
def test_a_malformed_frame_yields_an_empty_payload(lecteur: str) -> None:
    """
    Une trame qui n'est pas un dictionnaire vient d'un client cassé ou
    d'un envoi tronqué. Rendre "" laisse le serveur répondre proprement ;
    laisser passer ferait planter le handler WebSocket.
    """
    from api import protocol

    assert getattr(protocol, lecteur)("pas un dictionnaire") == ""
    assert getattr(protocol, lecteur)(None) == ""


# ══ 9. AURA — YouTube sert autant un cours qu'un clip ═════════════════

def test_a_lesson_on_youtube_is_learning_not_entertainment() -> None:
    """
    Le titre tranche : « tutoriel Python — YouTube » est du travail, pas
    de la détente. Sans cet arbitrage, Luca's prendrait un ton badin
    pendant que Cyril apprend.
    """
    from core.aura_modes import AuraMode, AuraModeEngine

    # ⚠️ Le titre doit déclencher ENTERTAINMENT et SEULEMENT lui :
    # "tutoriel" est à la fois marqueur LEARNING et marqueur d'arbitrage,
    # donc LEARNING gagnerait dès l'étape 5 et l'arbitrage ne servirait
    # jamais. "apprendre" n'est QUE marqueur d'arbitrage : c'est le seul
    # genre de titre qui exerce vraiment cette ligne.
    moteur = AuraModeEngine()
    assert moteur.detect("Apprendre le piano - YouTube", "chrome") is AuraMode.LEARNING
    # Contrôle : sans marqueur d'arbitrage, YouTube reste du loisir.
    assert moteur.detect("Clip de musique - YouTube", "chrome") is AuraMode.ENTERTAINMENT


# ══ 10. Finance — lignes vides et en-tête introuvable ═════════════════

def test_an_empty_row_ends_the_file_rather_than_becoming_a_transaction(tmp_path) -> None:
    """
    Les relevés bancaires finissent souvent par des lignes vides. Les
    convertir produirait des transactions fantômes à 0 €.
    """
    from modules.finance_manager import FinanceManager

    csv = tmp_path / "releve.csv"
    csv.write_text(
        "date,libelle,montant\n2026-01-05,CARREFOUR,-10\n,,\n",
        encoding="utf-8",
    )
    manager = FinanceManager()
    manager.import_csv(str(csv))
    assert len(manager.transactions) == 1


def test_a_header_hidden_too_deep_is_given_up_on(tmp_path) -> None:
    """
    Le scan d'en-tête s'arrête après HEADER_SCAN_LIMIT lignes. Sans cette
    borne, un fichier qui n'est pas un relevé serait parcouru en entier
    avant d'échouer.
    """
    from modules.finance_manager import (
        HEADER_SCAN_LIMIT,
        CSVFormatError,
        FinanceManager,
    )

    csv = tmp_path / "pas_un_releve.csv"
    bourrage = "\n".join(f"ligne de garniture {i}" for i in range(HEADER_SCAN_LIMIT + 5))
    csv.write_text(bourrage + "\ndate,libelle,montant\n2026-01-05,X,-10\n", encoding="utf-8")

    with pytest.raises(CSVFormatError):
        FinanceManager().import_csv(str(csv))


# ══ 11. Le label noyé dans une phrase ═════════════════════════════════

def test_a_label_buried_in_a_sentence_is_still_read(monkeypatch) -> None:
    """
    Un modèle à raisonnement rend rarement le mot seul : il écrit « the
    answer is ECRAN ». Exiger l'égalité stricte jetterait une
    classification correcte pour une question de mise en forme.
    """
    from core import intent, ollama_client

    intent._CACHE.clear()
    monkeypatch.setattr(
        ollama_client, "post_chat",
        lambda url, payload, timeout=None: _ReponseClassifieur("the answer is ECRAN"),
    )
    try:
        assert _ask_classifier_reel("c'est écrit quoi ?") == "ECRAN"
    finally:
        intent._CACHE.clear()


def test_two_labels_at_once_mean_the_model_hesitates(monkeypatch) -> None:
    """
    Deux labels présents = le modèle hésite encore. Mieux vaut rendre
    None et laisser l'appelant retomber sur les mots-clés que trancher
    au hasard.
    """
    from core import intent, ollama_client

    intent._CACHE.clear()
    monkeypatch.setattr(
        ollama_client, "post_chat",
        lambda url, payload, timeout=None: _ReponseClassifieur("ECRAN ou DOCUMENTS"),
    )
    try:
        assert _ask_classifier_reel("question ambiguë") is None
    finally:
        intent._CACHE.clear()


# ══ 12. World Model — fenêtre sans processus ══════════════════════════

def test_a_window_without_a_process_id_yields_no_name(monkeypatch) -> None:
    """
    Certaines fenêtres système ne rendent aucun PID. Rendre "" est la
    bonne réponse : inventer un nom tromperait la détection AURA.
    """
    import sys
    import types

    import core.world_model as wm

    faux_gui = types.ModuleType("win32gui")
    faux_gui.GetForegroundWindow = lambda: 42  # type: ignore[attr-defined]
    faux_process = types.ModuleType("win32process")
    faux_process.GetWindowThreadProcessId = lambda hwnd: (0, 0)  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "win32gui", faux_gui)
    monkeypatch.setitem(sys.modules, "win32process", faux_process)

    assert wm._get_active_process_name() == ""


# ══ 13. LucasCore — les dégradations du pipeline visuel ═══════════════

def _core_nu():
    """Un LucasCore sans __init__ : ni base, ni LLM, ni World Model."""
    from core.lucas_core import LucasCore

    instance = LucasCore.__new__(LucasCore)
    instance.log_event = lambda event_type, details="": None  # type: ignore[method-assign]
    return instance


def test_a_vision_engine_that_fails_to_load_degrades_to_no_description(monkeypatch) -> None:
    """
    Si VisionManager ne se construit pas (paquet absent, modele manquant),
    la reponse continue SANS description d'image — jamais une exception au
    milieu d'un message.

    Chemin exerce : `_describe_camera_image`, celui des photos envoyees par
    le telephone (pont mobile).
    """
    journal: list[tuple[str, str]] = []
    instance = _core_nu()
    instance.log_event = (  # type: ignore[method-assign]
        lambda event_type, details="": journal.append((event_type, details))
    )

    class _Explose:
        def __init__(self, model=None):
            raise RuntimeError("modele VLM introuvable")

    monkeypatch.setattr("modules.vision_manager.VisionManager", _Explose)

    assert instance._describe_camera_image("photo.png", "que vois-tu ?") == ""
    assert any(t == "vision_failed" for t, _ in journal), "la panne doit etre tracee"


def test_an_ocr_that_reads_nothing_yields_no_block(monkeypatch) -> None:
    """
    Un ecran sans texte lisible ne doit pas produire un bloc OCR vide :
    le modele le prendrait pour du contexte et broderait dessus.
    """
    import core.lucas_core as lc

    monkeypatch.setattr(lc, "OCR_ENABLED", True)

    class _Vide:
        is_empty = True
        text = ""

    class _Moteur:
        def extract_text(self, chemin):
            return _Vide()

    monkeypatch.setattr("modules.ocr_engine.OCREngine", _Moteur)

    assert _core_nu()._read_screen_text("capture.png") == ""


def test_a_vlm_that_raises_mid_analysis_degrades_quietly(monkeypatch) -> None:
    """Meme doctrine : une panne d'analyse ne casse pas la reponse."""
    import core.lucas_core as lc

    monkeypatch.setattr(lc, "VLM_ENABLED", True)

    journal: list[tuple[str, str]] = []
    instance = _core_nu()
    instance.log_event = (  # type: ignore[method-assign]
        lambda event_type, details="": journal.append((event_type, details))
    )

    class _VisionCassee:
        def analyze_image(self, chemin, prompt):
            raise RuntimeError("CUDA out of memory")

    assert instance._describe_visual_context(_VisionCassee(), "capture.png", "?") == ""
    assert any(t == "vision_failed" for t, _ in journal)


# == 14. La fausse confirmation, corrigee avant d'etre memorisee =======

def test_a_false_success_claim_is_corrected_before_being_remembered(monkeypatch) -> None:
    """
    ⚠️ Le garde-fou le plus important de ce fichier (ROADMAP.md §5.31).

    Si AUCUNE action n'a reellement eu lieu mais que la reponse affirme le
    contraire, la correction est ajoutee AVANT l'enregistrement en
    memoire : une fausse confirmation gardee en base deviendrait un
    exemple a imiter au tour suivant (auto-imitation, §5.5).
    """
    import core.lucas_core as lc
    from core.lucas_core import FALSE_CLAIM_CORRECTION
    from test_memory_double import MemoryDouble

    class _Memoire(MemoryDouble):
        def __init__(self) -> None:
            super().__init__()
            self.actions: list[dict] = []
            self.messages_memorises: list[tuple[str, str]] = []

        def save_action(self, action, source, result):
            self.actions.append({"action": action, "source": source, "result": result})

        def save_message(self, role, texte):
            # ⚠️ `save_message`, pas `save_response` : c'est cette
            # methode qu'appelle `ask()` (l.1307). Ma premiere version
            # surveillait `save_response` et concluait a tort que la
            # version NON corrigee etait memorisee.
            self.messages_memorises.append((role, texte))

    instance = _core_nu()
    memoire = _Memoire()
    instance.memory = memoire  # type: ignore[assignment]  # double assume, voir test_memory_double.py
    instance._action_executed = False

    monkeypatch.setattr(lc, "route", lambda message, contexte="": "local")
    monkeypatch.setattr(lc, "ask_local", lambda messages: "Le Bloc-notes est lance.")
    monkeypatch.setattr(
        lc.LucasCore, "_build_messages",
        lambda self, *a, **k: [{"role": "user", "content": "ouvre le bloc note"}],
    )
    monkeypatch.setattr(lc.LucasCore, "recent_context", lambda self: "")

    reponse = instance.ask("ouvre le bloc note")

    assert FALSE_CLAIM_CORRECTION in reponse, "la fausse confirmation doit etre corrigee"
    assert memoire.actions, "la correction doit etre journalisee"
    assert memoire.actions[0]["result"] == "false_claim_corrected"
    memorise = [texte for role, texte in memoire.messages_memorises if role == "assistant"]
    assert memorise and FALSE_CLAIM_CORRECTION in memorise[0], (
        "c'est la version CORRIGEE qui doit etre memorisee — sinon elle "
        "deviendrait un exemple a imiter au tour suivant"
    )
