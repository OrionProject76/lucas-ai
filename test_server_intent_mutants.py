# test_server_intent_mutants.py — survivants du pont mobile et du classifieur
#
# ⚠️ Pourquoi ce fichier existe (06/08/2026)
# ------------------------------------------
# Troisième palier de la campagne de mutation, après `security/` et
# `core/lucas_core.py`.
#
# `api/server.py` est la seule surface du projet exposée au réseau, et
# `core/intent.py` décide quand l'écran de Cyril est lu. Un survivant y
# coûte plus cher qu'ailleurs.

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from api.server import app

# ⚠️ Capture AVANT que la fixture autouse de conftest.py ne remplace
# `_ask_classifier`. Meme motif que test_couverture_residuelle.py.
from core.intent import _ask_classifier as _ask_classifier_reel


@pytest.fixture(autouse=True)
def _sans_jeton(monkeypatch):
    """Isole ces tests du vrai API_TOKEN de la machine.

    Meme garde que dans test_server.py : sans elle, ces tests
    dependent silencieusement du .env du poste qui les execute, et
    toutes les connexions WebSocket sont refusees.
    """
    monkeypatch.setattr("api.server.API_TOKEN", "")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def fake_core_speaks(monkeypatch):
    """Un LucasCore qui repond sans base ni LLM."""
    import api.server as srv

    class _FauxCore:
        def ask(self, message, image_path=None, allow_screen_capture=True, on_activity=None):
            return "bonjour Cyril"

        def recent_context(self):
            return ""

        def close(self):
            pass

    monkeypatch.setattr(srv, "LucasCore", _FauxCore)


# ══ api/server.py:132 — CORS : aucun identifiant de session ═══════════

def test_cors_never_allows_credentials() -> None:
    """
    ⚠️ Réglage de sécurité, pas de confort.

    `allow_credentials=True` autoriserait le navigateur à joindre cookies
    et en-têtes d'authentification aux requêtes CROISÉES. Le jeton de
    Luca's voyage par `Authorization`, jamais par cookie : il n'y a rien à
    autoriser, et l'autoriser élargirait la surface pour rien.

    Mutant 132 : `allow_credentials=False` -> `True`.
    """
    from starlette.middleware.cors import CORSMiddleware

    cors = [m for m in app.user_middleware if m.cls is CORSMiddleware]
    assert cors, "le middleware CORS doit être installé"
    assert cors[0].kwargs["allow_credentials"] is False, (
        "aucun identifiant de session ne doit traverser une requête croisée"
    )


# ══ api/server.py:444 — une image malformée est refusée, pas écrite ═══

def test_a_malformed_base64_image_is_rejected_not_written_to_disk() -> None:
    """
    Sans `validate=True`, `b64decode` IGNORE les caractères invalides et
    rend des octets tronqués. Un fichier illisible partirait alors à
    l'OCR, qui échouerait bien plus loin — sur un symptôme sans rapport
    avec la cause.

    Mieux vaut une erreur claire côté client qu'un fichier vide analysé.

    Mutant 444 : `validate=True` -> `False`.
    """
    from api.server import _save_base64_image

    # ⚠️ L'ENTRÉE doit discriminer. Ma première version envoyait
    # « !!! ceci n'est pas du base64 !!! » : elle échoue des DEUX côtés —
    # avec validate=True pour caractère interdit, avec validate=False pour
    # padding incorrect. Même résultat, mutation équivalente, test inutile.
    #
    # « QUJD! » est le cas qui sépare : validate=False ignore le « ! » et
    # rend silencieusement b"ABC" ; validate=True refuse. C'est exactement
    # le danger — des octets tronqués écrits sur disque puis envoyés à
    # l'OCR, qui échouerait bien plus loin.
    with pytest.raises(Exception):  # noqa: B017 — le refus compte, pas sa forme
        _save_base64_image("QUJD!")


def test_a_valid_base64_image_is_written(tmp_path) -> None:
    """Contrôle inverse : une image valide doit bien arriver sur disque."""
    import os

    from api.server import _save_base64_image

    contenu = b"\xff\xd8\xff\xe0 faux JPEG"
    chemin = _save_base64_image(base64.b64encode(contenu).decode())
    try:
        assert os.path.exists(chemin)
        with open(chemin, "rb") as f:
            assert f.read() == contenu
    finally:
        os.unlink(chemin)


# ══ api/server.py:480/482 — négociation du sous-protocole WebSocket ═══

def test_the_announced_subprotocol_is_echoed_back(client) -> None:
    """
    La PWA annonce `lucas.v1`. Le serveur doit le renvoyer, sinon le
    navigateur considère la négociation échouée et ferme la connexion.

    Mutant 482 : `if WS_SUBPROTOCOL in proposes` -> `not in`. Inversé, le
    serveur renvoyait le protocole quand il N'était PAS proposé, et rien
    quand il l'était — la PWA ne se connectait plus du tout.
    """
    from api.server import WS_SUBPROTOCOL

    with client.websocket_connect("/ws", subprotocols=[WS_SUBPROTOCOL]) as ws:
        assert ws.accepted_subprotocol == WS_SUBPROTOCOL


def test_a_client_announcing_nothing_still_connects(client) -> None:
    """
    Godot et les tests se connectent SANS annoncer de sous-protocole.

    Mutant 480 : `scope.get("subprotocols") or []` -> `and`. Avec `and`,
    l'absence de sous-protocole donnait `None`, et le test d'appartenance
    juste après levait un TypeError — la connexion tombait.
    """
    with client.websocket_connect("/ws") as ws:
        assert ws.accepted_subprotocol is None
        ws.receive_json()  # la connexion vit : le serveur pousse son état


# ══ api/server.py:514 — le message d'accueil vient bien de Luca's ═════

def test_the_welcome_message_is_attributed_to_luca(client) -> None:
    """
    `from_luca=True` décide de quel côté le message s'affiche dans la PWA.
    À False, « Luca's est connectée. » apparaîtrait comme si CYRIL l'avait
    écrit — une phrase qu'il n'a jamais tapée, dans son propre fil.

    Mutant 514 : `from_luca=True` -> `False`.
    """
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "hello", "client": "lucas_pwa"})
        for _ in range(10):
            message = ws.receive_json()
            if message.get("type") == "chat":
                # ⚠️ Le CHAMP s'appelle `from_lucas` (avec un s), le
                # PARAMÈTRE `from_luca`. Écart hérité du renommage du
                # 02/08/2026 (ROADMAP §6) : le contrat WebSocket a été
                # renommé des deux côtés, la signature Python non.
                assert message["from_lucas"] is True, (
                    "le message d'accueil doit être attribué à Luca's"
                )
                return
    pytest.fail("aucun message d'accueil reçu")


# ══ core/intent.py:177 — l'intention est immuable ════════════════════

def test_an_intent_cannot_be_rewritten_after_classification() -> None:
    """
    Même garantie que `SecurityStatus` : une intention se lit, elle ne se
    corrige pas après coup. Sans gel, un appelant pourrait transformer un
    « AUCUN » en « ÉCRAN » et déclencher une capture non décidée par le
    classifieur.

    Mutant 177 : `@dataclass(frozen=True)` -> `False`.
    """
    import dataclasses

    from core.intent import Intent

    intention = Intent(needs_screen=False, needs_documents=False, source="keywords")
    with pytest.raises(dataclasses.FrozenInstanceError):
        intention.needs_screen = True  # type: ignore[misc]  # c'est l'interdit testé


# ══ core/intent.py:224 — qui parle dans le contexte ══════════════════

def test_the_context_names_cyril_and_luca_on_the_right_side() -> None:
    """
    Le contexte transmis au classifieur nomme chaque tour. Inverser les
    étiquettes lui ferait lire la réponse de Luca's comme une question de
    Cyril — et classer l'intention de la mauvaise phrase.

    Mutant 224 : `role == "user"` -> `!=`.
    """
    from core.intent import format_context

    contexte = format_context([
        ("user", "quel est le total ?"),
        ("assistant", "1847 euros."),
    ])
    assert "Cyril : quel est le total" in contexte
    assert "Toi : 1847 euros" in contexte


# ══ core/intent.py:339/340 — l'héritage d'intention ne boucle pas ════

def test_an_elliptical_question_inherits_from_the_previous_one(monkeypatch) -> None:
    """
    « et pour 2024 ? » n'a de sens que par rapport à la question d'avant.
    L'intention est donc héritée.

    Mutant 340 : `_inherit=False` -> `True`. L'appel récursif reprendrait
    le chemin d'héritage — une question elliptique dont la précédente est
    elle-même elliptique ferait remonter la chaîne sans fin.
    """
    from core import intent

    intent._CACHE.clear()
    monkeypatch.setattr(intent, "_ask_classifier", lambda question, context="": "ECRAN")
    try:
        resultat = intent.classify("et celle-là ?", "Cyril : c'est écrit quoi ?\nToi : ...")
        assert resultat.needs_screen is True
    finally:
        intent._CACHE.clear()


def test_a_question_identical_to_the_previous_one_does_not_recurse(monkeypatch) -> None:
    """
    Mutant 339 : `precedente and precedente != question` -> `or`. Avec
    `or`, une question identique à la précédente hérite d'elle-même — et
    le classifieur est alors appelé avec un contexte VIDE, donc privé de
    l'information même qui aurait permis de trancher.

    ⚠️ Le stub doit rendre un VRAI label. Ma première version rendait
    `None` : l'héritage échouait alors des deux côtés (un repli mots-clés
    ne s'hérite pas), et le mutant restait indiscernable.

    Vérifié en direct — `source` vaut « llm » sur l'original, « inherited »
    sur le mutant.
    """
    from core import intent

    intent._CACHE.clear()
    monkeypatch.setattr(intent, "_ask_classifier", lambda question, context="": "ECRAN")
    try:
        # La question EST la précédente.
        resultat = intent.classify("et alors ?", "Cyril : et alors ?\nToi : ...")
        assert resultat.source == "llm", (
            "une question identique à la précédente ne peut pas hériter "
            "d'elle-même : c'est le classifieur qui doit trancher, avec le "
            "vrai contexte"
        )
    finally:
        intent._CACHE.clear()


# ══ core/intent.py:354 — le classifieur coupé reste coupé ════════════

def test_a_disabled_classifier_is_never_called(monkeypatch) -> None:
    """
    `INTENT_CLASSIFIER_ENABLED` est l'interrupteur qui garantit qu'aucun
    appel LLM n'a lieu pour classer. Coupé, il doit l'être vraiment :
    c'est le repli mots-clés qui prend le relais.

    Mutant 354 : `INTENT_CLASSIFIER_ENABLED and question.strip()` -> `or`.
    Avec `or`, une question non vide suffisait à appeler le modèle malgré
    l'interrupteur.
    """
    from core import intent

    def _interdit(question, context=""):
        raise AssertionError("le classifieur est coupé, il ne doit pas être appelé")

    intent._CACHE.clear()
    monkeypatch.setattr(intent, "INTENT_CLASSIFIER_ENABLED", False)
    monkeypatch.setattr(intent, "_ask_classifier", _interdit)
    try:
        resultat = intent.classify("qu'est-ce qui est affiché ?")
        assert resultat.source == "keywords", "le repli mots-clés doit prendre le relais"
    finally:
        intent._CACHE.clear()


# ══ core/intent.py:260 — la requête du classifieur n'est pas streamée ══

def test_the_classifier_request_is_not_streamed(monkeypatch) -> None:
    """
    La réponse est lue d'un bloc (`response.json()`). En streaming, Ollama
    rend une suite de fragments JSON et le parsing échoue — le classifieur
    retomberait silencieusement sur les mots-clés.

    Mutant 260 : `"stream": False` -> `True`.
    """
    from core import intent, ollama_client

    envoyes: list[dict] = []

    class _Reponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "ECRAN"}}

    def _capture(url, payload, timeout=None):
        envoyes.append(payload)
        return _Reponse()

    intent._CACHE.clear()
    monkeypatch.setattr(ollama_client, "post_chat", _capture)
    try:
        _ask_classifier_reel("c'est écrit quoi ?")
    finally:
        intent._CACHE.clear()

    assert envoyes, "le classifieur doit avoir émis une requête"
    assert envoyes[0]["stream"] is False, (
        "en streaming, la réponse ne serait pas lisible d'un bloc"
    )


# ══ api/server.py:722 / 767 — un fichier déjà disparu ne fait pas tomber ══

def test_a_vanished_temp_image_does_not_break_the_answer(client, monkeypatch) -> None:
    """
    Le fichier temporaire est supprimé dans un `finally`. S'il a déjà
    disparu — nettoyage système, antivirus, dossier temp purgé — un
    `unlink()` sans `missing_ok` lèverait DANS le finally, écrasant la
    réponse déjà calculée par une exception sans rapport.

    Mutant 722 : `unlink(missing_ok=True)` -> `False`.
    """
    import api.server as srv

    class _FauxCore:
        def ask(self, message, image_path=None, allow_screen_capture=True, on_activity=None):
            return "je vois une image"

        def recent_context(self):
            return ""

        def close(self):
            pass

    monkeypatch.setattr(srv, "LucasCore", _FauxCore)
    # Un chemin qui n'existe PAS : exactement l'état d'un fichier volatilisé.
    monkeypatch.setattr(srv, "_save_base64_image", lambda b64: "C:/introuvable/x.jpg")

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "image", "image_base64": "QUJD", "message": "que vois-tu ?"})
        for _ in range(15):
            message = ws.receive_json()
            if message.get("type") == "chat" and message.get("from_lucas"):
                assert "je vois une image" in message["text"]
                return
    pytest.fail("la réponse n'est jamais arrivée")


def test_a_vanished_audio_file_does_not_break_the_speech(client, fake_core_speaks, monkeypatch) -> None:
    """
    Même piège côté voix : le fichier audio est lu puis supprimé. S'il a
    disparu entre les deux, le `finally` ne doit pas emporter la réponse.

    Mutant 767 : `unlink(missing_ok=True)` -> `False`.
    """
    import api.server as srv

    class _Voix:
        def synthesize_routed(self, text, question=""):
            return "C:/introuvable/son.mp3"

    monkeypatch.setattr(srv, "_voice_manager", _Voix())
    # La lecture réussit (contenu simulé), mais le fichier n'existe pas :
    # c'est la suppression qui doit tolérer son absence.
    monkeypatch.setattr(srv, "_read_audio_b64", lambda chemin: "RkFLRQ==")

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "bonjour", "speak": True})
        for _ in range(15):
            message = ws.receive_json()
            if message.get("type") == "speech":
                assert message["audio_base64"] == "RkFLRQ=="
                return
    pytest.fail("aucun message vocal reçu")
