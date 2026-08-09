# test_server.py — API FastAPI de Luca's
#
# Remplace l'ancien contenu, qui lançait un vrai serveur uvicorn : pytest
# collectait test_server() comme un test et la suite se bloquait
# indéfiniment. D'où son exclusion dans le justfile — exclusion désormais
# inutile.
#
# LucasCore est mocké : aucun appel à Ollama, aucune écriture dans
# memory/lucas_memory.db.

from __future__ import annotations

import base64
import os

import pytest
from fastapi.testclient import TestClient

# ⚠️ Type PRÉCIS, pas `Exception` : ces trois tests gardent le contrôle du
# jeton. Avec `pytest.raises(Exception)`, ils passeraient au vert même si
# la connexion échouait pour une raison sans rapport (URL fautive, double
# cassé) — un test d'authentification qui se contente de « quelque chose
# a échoué » ne prouve pas que le refus vient du jeton. Type constaté en
# exécutant réellement le cas (06/08/2026).
from starlette.websockets import WebSocketDisconnect

from api.server import app


@pytest.fixture(autouse=True)
def _no_token_by_default(monkeypatch):
    """
    Isole la suite de la vraie valeur d'API_TOKEN dans .env de la machine.

    ⚠️ Sans ceci, ces tests dépendent silencieusement du poste où ils
    tournent : une fois un vrai jeton renseigné dans .env (pont mobile,
    02/08/2026), tous les tests WebSocket se sont mis à échouer — la
    connexion se refusait faute de jeton fourni. Un test ne doit jamais
    dépendre d'un secret local ; les tests qui veulent un vrai jeton le
    posent eux-mêmes via monkeypatch (ex. fixture ci-dessous), ce qui
    prévaut sur ce défaut pour la durée du test grâce à monkeypatch.
    """
    monkeypatch.setattr("api.server.API_TOKEN", "")


@pytest.fixture(autouse=True)
def _no_real_security_status_by_default(monkeypatch):
    """
    Isole la suite des vraies bases SQLite de la machine
    (data/lucas_daemon.db, memory/lucas_memory.db).

    ⚠️ Sans ceci, chaque test WebSocket ferait un vrai accès disque vers
    ces deux fichiers dès la connexion (_push_security_status), et son
    résultat dépendrait de si lucas_daemon.py tourne réellement sur le
    poste qui exécute la suite — même défaut que celui corrigé pour
    API_TOKEN ci-dessus. Un test explicite (voir fake_security_status)
    prévaut sur ce défaut pour sa durée.
    """
    from security.status import SecurityStatus

    monkeypatch.setattr(
        "api.server.get_security_status",
        lambda: SecurityStatus(
            active=False, last_scan_at=None, findings_24h=0, latest_summary=None
        ),
    )


@pytest.fixture(autouse=True)
def _no_real_tts_by_default(monkeypatch):
    """
    Isole la suite du vrai VoiceManager (edge_tts part sur le réseau,
    Piper charge un modèle .onnx) — même défaut que ci-dessus pour
    API_TOKEN et l'état de sécurité. La quasi-totalité des tests
    n'envoient jamais "speak": true, donc ce chemin n'est même pas
    emprunté ; ce garde-fou couvre les rares tests qui l'envoient sans
    poser fake_voice explicitement.
    """

    class _SilentVoiceManager:
        def synthesize_routed(self, text, question=""):
            return None

    monkeypatch.setattr("api.server._voice_manager", _SilentVoiceManager())


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def fake_core(monkeypatch):
    """Remplace LucasCore par un double qui n'ouvre ni base ni LLM."""
    calls: dict[str, object] = {}

    class _FakeCore:
        def ask(
            self,
            message: str,
            image_path: str | None = None,
            allow_screen_capture: bool = True,
            on_activity=None,
        ) -> str:
            calls["asked"] = message
            calls["asked_image_path"] = image_path
            calls["asked_allow_screen_capture"] = allow_screen_capture
            # Capturé PENDANT l'appel : le fichier temporaire est supprimé
            # juste après, dans le finally de websocket_endpoint.
            calls["image_existed_during_call"] = (
                image_path is not None and os.path.exists(image_path)
            )
            if on_activity is not None:
                on_activity("routed", "question reçue — traitée en LOCAL (fake)")
                on_activity("answered", "réponse prête (0.0 s)")
            return f"réponse à « {message} »"

        def history(self):
            return [("user", "bonjour"), ("assistant", "salut")]

        def recent_context(self):
            # ⚠️ Manquait jusqu'au 02/08/2026 : should_use_vision(message,
            # lucas.recent_context()) levait AttributeError sur ce double,
            # rattrapée par le except large d'api/server.py qui retombe
            # sur regarde=False. Aucun test n'a jamais pu vérifier l'état
            # WATCHING via ce fixture avant que ça se voie enfin.
            return ""

        def close(self):
            calls["closed"] = True

    monkeypatch.setattr("api.server.LucasCore", _FakeCore)
    return calls


@pytest.fixture
def fake_stt(monkeypatch):
    """
    Remplace le moteur STT partagé par un double — aucun modèle Whisper
    chargé, aucun fichier temporaire écrit.
    """
    from modules.stt_engine import STTUnavailable, TranscriptResult

    calls: dict[str, object] = {}

    class _FakeSTT:
        def __init__(self, texte="audio transcrit", boom=None):
            self.texte = texte
            self.boom = boom

        def transcribe_base64(self, audio_base64, suffix=".wav"):
            calls["audio_base64"] = audio_base64
            if self.boom:
                raise self.boom
            return TranscriptResult(
                text=self.texte, language="fr", confidence=0.9, duration_seconds=1.5,
            )

    double = _FakeSTT()
    monkeypatch.setattr("api.server._stt_engine", double)
    calls["_double"] = double  # pour permuter texte/boom depuis un test
    calls["_STTUnavailable"] = STTUnavailable
    return calls


@pytest.fixture
def fake_voice(monkeypatch, tmp_path):
    """
    Remplace _voice_manager par un double qui produit un vrai petit
    fichier (le serveur le lit et l'encode en base64) sans jamais
    toucher edge_tts ni Piper.
    """
    calls: dict[str, object] = {}
    audio_path = tmp_path / "output.mp3"
    audio_path.write_bytes(b"FAKE-MP3-BYTES")

    class _FakeVoiceManager:
        def synthesize_routed(self, text, question=""):
            calls["text"] = text
            calls["question"] = question
            return str(audio_path)

    monkeypatch.setattr("api.server._voice_manager", _FakeVoiceManager())
    calls["_audio_path"] = audio_path
    return calls


# ── REST ──────────────────────────────────────────────────────────────

def test_status_confirms_the_server_runs(client) -> None:
    response = client.get("/status")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_system_returns_the_world_model_snapshot(client) -> None:
    response = client.get("/system")
    assert response.status_code == 200
    # `active_process` ajouté le 05/08/2026 (détection AURA — un terminal
    # affiche ce que Cyril y écrit, jamais son propre nom). Exposé ici au
    # même titre qu'`active_window`, et strictement moins révélateur que
    # lui : « chrome » ne dit rien, « releve_bancaire.pdf » si. Cette route
    # sert le téléphone de Cyril sur le réseau local, jamais le cloud —
    # la règle 3 de CLAUDE.md porte sur ce qui SORT de la machine.
    assert set(response.json()) == {
        "cpu_percent", "ram_percent", "gpu_percent", "active_window",
        "active_process", "local_time",
    }


def test_system_reports_a_missing_dependency_clearly(client, monkeypatch) -> None:
    """Une dépendance manquante pour le World Model doit devenir un 500 explicite, pas un plantage brut."""
    from api import server

    def _raise():
        raise ImportError("GPUtil absent")

    monkeypatch.setattr(server, "get_snapshot", _raise)

    response = client.get("/system")
    assert response.status_code == 500
    assert "Dépendance manquante" in response.json()["detail"]


def test_chat_returns_the_answer(client, fake_core) -> None:
    response = client.post("/chat", json={"message": "quelle heure il est"})
    assert response.status_code == 200
    assert "quelle heure il est" in response.json()["response"]


def test_chat_rejects_an_empty_message(client, fake_core) -> None:
    assert client.post("/chat", json={"message": "   "}).status_code == 400


def test_chat_always_closes_the_core(client, fake_core) -> None:
    """
    Sans fermeture, chaque requête laisserait une connexion SQLite
    ouverte — le serveur finirait par saturer.
    """
    client.post("/chat", json={"message": "test"})
    assert fake_core.get("closed") is True


def test_history_is_returned_as_role_content_pairs(client, fake_core) -> None:
    payload = client.get("/history").json()["history"]
    assert payload == [
        {"role": "user", "content": "bonjour"},
        {"role": "assistant", "content": "salut"},
    ]


# ── Semantic Desktop (contrepartie mobile, 03/08/2026) ─────────────────


@pytest.fixture
def fake_semantic_desktop(monkeypatch):
    """Remplace SemanticDesktop par un double — aucun ChromaDB réel touché."""

    class _FakeDesktop:
        def list_documents(self):
            return ["bulletin_juillet.pdf", "cv.pdf"]

        def group_by_period(self):
            return {"2025": ["bulletin_juillet.pdf"], "sans période": ["cv.pdf"]}

        def related_documents(self, source_id, top_k=3):
            return [f"proche_de_{source_id}_{i}" for i in range(top_k)]

    monkeypatch.setattr("api.server.SemanticDesktop", _FakeDesktop)
    return _FakeDesktop


def test_documents_lists_indexed_sources(client, fake_semantic_desktop) -> None:
    payload = client.get("/documents").json()
    assert payload == {"documents": ["bulletin_juillet.pdf", "cv.pdf"]}


def test_documents_periods_groups_by_year(client, fake_semantic_desktop) -> None:
    payload = client.get("/documents/periods").json()
    assert payload == {
        "periods": {"2025": ["bulletin_juillet.pdf"], "sans période": ["cv.pdf"]}
    }


def test_documents_related_respects_top_k(client, fake_semantic_desktop) -> None:
    payload = client.get("/documents/cv.pdf/related?top_k=2").json()
    assert payload == {"related": ["proche_de_cv.pdf_0", "proche_de_cv.pdf_1"]}


def test_documents_related_defaults_top_k_to_three(client, fake_semantic_desktop) -> None:
    payload = client.get("/documents/cv.pdf/related").json()
    assert len(payload["related"]) == 3


def test_documents_endpoints_require_the_token(client, fake_semantic_desktop, monkeypatch) -> None:
    """
    Même garde que /history : les noms de fichiers personnels de Cyril
    (bulletins, attestations...) sont aussi révélateurs que l'historique.
    """
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    assert client.get("/documents").status_code == 401
    assert client.get("/documents/periods").status_code == 401
    assert client.get("/documents/cv.pdf/related").status_code == 401


# ── Finance CSV (contrepartie mobile, 03/08/2026) ──────────────────────


class _FakeFinanceManagerForAPI:
    """
    Double minimal — même interface que modules.finance_manager.FinanceManager,
    sans toucher au disque. `load_directory` est importé PARESSEUSEMENT
    dans l'endpoint (voir api/server.py, même motif que core/lucas_core.py) :
    monkeypatché sur "modules.finance_manager.load_directory", pas sur
    "api.server.load_directory", qui n'existe pas en tant qu'attribut.
    """

    def __init__(self, transactions: list) -> None:
        self.transactions = transactions

    def get_balance(self) -> float:
        return sum(t["montant"] for t in self.transactions)

    def get_income_total(self) -> float:
        return sum(t["montant"] for t in self.transactions if t["montant"] > 0)

    def get_expense_total(self) -> float:
        return abs(sum(t["montant"] for t in self.transactions if t["montant"] < 0))

    def get_expenses_by_category(self) -> dict:
        return {"Alimentation": 84.3}

    def get_uncategorized(self) -> list:
        return []


@pytest.fixture
def fake_finance_with_data(monkeypatch):
    from datetime import datetime

    # Dates naïves délibérées : elles imitent ce que `finance_manager`
    # produit en lisant un CSV bancaire, qui ne porte aucun fuseau.
    # Les rendre conscientes ici ferait diverger le double du réel.
    transactions = [
        {"date": datetime(2026, 1, 2), "libelle": "Virement salaire", "montant": 2400.0, "categorie": "Revenus"},  # noqa: DTZ001
        {"date": datetime(2026, 1, 5), "libelle": "CARREFOUR", "montant": -84.3, "categorie": "Alimentation"},  # noqa: DTZ001
    ]
    manager = _FakeFinanceManagerForAPI(transactions)
    monkeypatch.setattr("modules.finance_manager.load_directory", lambda: (manager, []))
    return manager


@pytest.fixture
def fake_finance_empty(monkeypatch):
    manager = _FakeFinanceManagerForAPI([])
    monkeypatch.setattr("modules.finance_manager.load_directory", lambda: (manager, []))
    return manager


def test_finance_summary_reports_real_numbers(client, fake_finance_with_data) -> None:
    payload = client.get("/finance/summary").json()
    assert payload["has_data"] is True
    assert payload["transaction_count"] == 2
    assert payload["balance"] == pytest.approx(2315.7)
    assert payload["income"] == pytest.approx(2400.0)
    assert payload["expenses"] == pytest.approx(84.3)
    assert payload["period"] == {"start": "2026-01-02", "end": "2026-01-05"}


def test_finance_summary_says_no_data_explicitly_when_empty(client, fake_finance_empty) -> None:
    """Jamais un résumé vide en silence — has_data=False, sans inventer de chiffres."""
    payload = client.get("/finance/summary").json()
    assert payload == {"has_data": False, "skipped_files": []}


def test_finance_summary_requires_the_token(client, fake_finance_with_data, monkeypatch) -> None:
    """Un solde ou une dépense nommée est une donnée ultra-sensible (CLAUDE.md règle 3)."""
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    assert client.get("/finance/summary").status_code == 401


# ── Workspace Luca's (IDEAS.md #102, E-1) ───────────────────────────────


def test_workspace_summary_requires_the_token(client, monkeypatch) -> None:
    """Noms de rapports et objectifs prospectifs sont sensibles (CLAUDE.md règle 3)."""
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    assert client.get("/workspace/summary").status_code == 401


def test_workspace_summary_relays_real_data_without_transformation(client, monkeypatch) -> None:
    """
    La route ne fait que relayer modules.workspace_manager.summary() —
    vérifié en mockant cette fonction plutôt que le disque/la DB, pour ne
    tester ici QUE le câblage de la route (le contenu de summary() est
    couvert par test_workspace_manager.py).
    """
    fake_summary = {
        "reports": [{"filename": "a.md", "title": "A", "size_bytes": 10, "modified_at": "2026-08-08T00:00:00+00:00"}],
        "pending_requests": [],
        "recent_actions": [{"action": "open_app:calc", "source": "chat", "result": "executed", "params": None, "created_at": "2026-08-08 10:00:00"}],
        "objectives": [{"id": 1, "memory_type": "prospective", "content": "Objectif retraite", "confidence": 1.0, "importance": 0.5}],
    }
    monkeypatch.setattr("api.server.workspace_summary", lambda: fake_summary)

    assert client.get("/workspace/summary").json() == fake_summary


# ── Disposition du Workspace (glisser-déposer + tailles, 09/08/2026) ───


def test_workspace_layout_get_requires_the_token(client, monkeypatch) -> None:
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    assert client.get("/workspace/layout").status_code == 401


def test_workspace_layout_put_requires_the_token(client, monkeypatch) -> None:
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    payload = {"order": ["reports", "requests", "actions", "objectives"], "sizes": {}}
    assert client.put("/workspace/layout", json=payload).status_code == 401


def test_workspace_layout_get_relays_real_data_without_transformation(client, monkeypatch) -> None:
    fake_layout = {
        "order": ["objectives", "actions", "requests", "reports"],
        "sizes": {"reports": "S", "requests": "L", "actions": "XL", "objectives": "M"},
    }
    monkeypatch.setattr("api.server.workspace_get_layout", lambda: fake_layout)

    assert client.get("/workspace/layout").json() == fake_layout


def test_workspace_layout_put_saves_and_confirms(client, monkeypatch) -> None:
    calls: dict = {}

    def fake_save(order, sizes):
        calls["order"] = order
        calls["sizes"] = sizes

    monkeypatch.setattr("api.server.workspace_save_layout", fake_save)

    payload = {
        "order": ["actions", "reports", "objectives", "requests"],
        "sizes": {"reports": "M", "requests": "S", "actions": "L", "objectives": "XL"},
    }
    response = client.put("/workspace/layout", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert calls["order"] == payload["order"]
    assert calls["sizes"] == payload["sizes"]


def test_workspace_layout_put_rejects_an_invalid_layout(client, monkeypatch) -> None:
    """400, pas 500 — une disposition invalide est une entrée refusée, pas une panne serveur."""
    from modules.workspace_manager import InvalidLayout

    def fake_save(order, sizes):
        raise InvalidLayout("carte inconnue")

    monkeypatch.setattr("api.server.workspace_save_layout", fake_save)

    payload = {"order": ["reports"], "sizes": {}}
    response = client.put("/workspace/layout", json=payload)

    assert response.status_code == 400
    assert "carte inconnue" in response.json()["detail"]


# ── Zone sandbox du Workspace (E-3, 09/08/2026) ─────────────────────────
#
# Même discipline que le reste de cette section : on ne teste ici QUE le
# câblage de la route (jeton, relais, 400 propre) en mockant
# modules.sandbox_manager — le comportement réel (isolation, timeout,
# statuts) est couvert par test_sandbox_manager.py.


def test_workspace_sandbox_submit_requires_the_token(client, monkeypatch) -> None:
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    response = client.post("/workspace/sandbox/submit", json={"code": "print(1)"})
    assert response.status_code == 401


def test_workspace_sandbox_submit_relays_the_created_run(client, monkeypatch) -> None:
    calls: dict = {}
    fake_run = {"id": 1, "code": "print(1)", "status": "pending"}

    def fake_submit(code):
        calls["code"] = code
        return fake_run

    monkeypatch.setattr("api.server.sandbox_submit", fake_submit)

    response = client.post("/workspace/sandbox/submit", json={"code": "print(1)"})

    assert response.status_code == 200
    assert response.json() == fake_run
    assert calls["code"] == "print(1)"


def test_workspace_sandbox_submit_rejects_empty_code_with_400(client, monkeypatch) -> None:
    from modules.sandbox_manager import SandboxError

    def fake_submit(code):
        raise SandboxError("Le code proposé est vide.")

    monkeypatch.setattr("api.server.sandbox_submit", fake_submit)

    response = client.post("/workspace/sandbox/submit", json={"code": "   "})

    assert response.status_code == 400
    assert "vide" in response.json()["detail"]


def test_workspace_sandbox_execute_requires_the_token(client, monkeypatch) -> None:
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    assert client.post("/workspace/sandbox/1/execute").status_code == 401


def test_workspace_sandbox_execute_relays_the_result(client, monkeypatch) -> None:
    calls: dict = {}
    fake_result = {"id": 1, "status": "executed", "stdout": "1\n", "exit_code": 0}

    def fake_execute(run_id):
        calls["run_id"] = run_id
        return fake_result

    monkeypatch.setattr("api.server.sandbox_execute", fake_execute)

    response = client.post("/workspace/sandbox/1/execute")

    assert response.status_code == 200
    assert response.json() == fake_result
    assert calls["run_id"] == 1


def test_workspace_sandbox_execute_rejects_an_already_decided_run_with_400(client, monkeypatch) -> None:
    from modules.sandbox_manager import SandboxError

    def fake_execute(run_id):
        raise SandboxError("Proposition déjà tranchée (statut actuel : 'rejected').")

    monkeypatch.setattr("api.server.sandbox_execute", fake_execute)

    response = client.post("/workspace/sandbox/1/execute")

    assert response.status_code == 400
    assert "tranchée" in response.json()["detail"]


def test_workspace_sandbox_reject_requires_the_token(client, monkeypatch) -> None:
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    assert client.post("/workspace/sandbox/1/reject").status_code == 401


def test_workspace_sandbox_reject_relays_the_result(client, monkeypatch) -> None:
    fake_result = {"id": 1, "status": "rejected"}
    monkeypatch.setattr("api.server.sandbox_reject", lambda run_id: fake_result)

    response = client.post("/workspace/sandbox/1/reject")

    assert response.status_code == 200
    assert response.json() == fake_result


def test_workspace_sandbox_reject_rejects_an_unknown_id_with_400(client, monkeypatch) -> None:
    from modules.sandbox_manager import SandboxError

    def fake_reject(run_id):
        raise SandboxError("Proposition sandbox inconnue : 999999")

    monkeypatch.setattr("api.server.sandbox_reject", fake_reject)

    response = client.post("/workspace/sandbox/999999/reject")

    assert response.status_code == 400
    assert "inconnue" in response.json()["detail"]


# ── Poste de Commandement IA (E-5, 09/08/2026) ──────────────────────────


def test_capabilities_requires_the_token(client, monkeypatch) -> None:
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    assert client.get("/capabilities").status_code == 401


def test_capabilities_relays_the_registry_without_transformation(client, monkeypatch) -> None:
    from modules.capability_registry import Capability

    fake_capabilities = [
        Capability(
            name="Test", category="Test", description="Une capacité de test",
            status="actif", detail="test_server.py",
        ),
    ]
    monkeypatch.setattr("api.server.list_capabilities", lambda: fake_capabilities)
    monkeypatch.setattr("api.server.CAPABILITY_REGISTRY_VERIFIED_AT", "2026-01-01")

    response = client.get("/capabilities")

    assert response.status_code == 200
    assert response.json() == {
        "verified_at": "2026-01-01",
        "capabilities": [
            {
                "name": "Test", "category": "Test", "description": "Une capacité de test",
                "status": "actif", "detail": "test_server.py",
            },
        ],
    }


# ── WebSocket ─────────────────────────────────────────────────────────

def _next_of_type(ws, message_type: str, limit: int = 12) -> dict:
    """
    Lit jusqu'au prochain message du type demandé.

    Le canal transporte aussi la charge machine, poussée en continu pour
    le HUD Godot. Un client ne peut donc pas supposer un ordre strict :
    il dispatche par type, comme le fait websocket_client.gd. Les tests
    doivent en faire autant, sinon ils testent une hypothèse que le vrai
    client ne partage pas.
    """
    for _ in range(limit):
        message = ws.receive_json()
        if message.get("type") == message_type:
            return message
    raise AssertionError(f"aucun message « {message_type} » reçu")


def test_websocket_announces_idle_on_connection(client) -> None:
    with client.websocket_connect("/ws") as ws:
        first = _next_of_type(ws, "avatar_state")
        assert first["state"] == "idle"


@pytest.fixture
def fake_security_status(monkeypatch):
    """
    Remplace la lecture des deux bases SQLite (data/lucas_daemon.db,
    memory/lucas_memory.db) par un état fixe — aucun test ne doit dépendre
    de ce qui tourne réellement sur la machine qui l'exécute.
    """
    from security.status import SecurityStatus

    status = SecurityStatus(
        active=True,
        last_scan_at="2026-08-02T21:00:00",
        findings_24h=2,
        latest_summary="Process svch0st.exe imite svchost.exe",
    )
    monkeypatch.setattr("api.server.get_security_status", lambda: status)
    return status


def test_websocket_pushes_security_status(client, fake_security_status) -> None:
    """Panneau des privilèges (IDEAS.md #78) : l'état arrive sans le demander."""
    with client.websocket_connect("/ws") as ws:
        message = _next_of_type(ws, "security_status")

    assert message["active"] is True
    assert message["findings_24h"] == 2
    assert message["last_scan_at"] == "2026-08-02T21:00:00"
    assert message["latest_summary"] == "Process svch0st.exe imite svchost.exe"


def test_websocket_reports_an_inactive_daemon_plainly(client) -> None:
    """
    Un daemon éteint doit se voir clairement, pas disparaître en silence
    — même principe que le RAG sans résultat (core/lucas_core.py) : ne
    jamais laisser deviner un état qu'on peut vérifier. C'est aussi le
    défaut de _no_real_security_status_by_default, donc rien à patcher
    ici : ce test documente ce que ce défaut vérifie vraiment.
    """
    with client.websocket_connect("/ws") as ws:
        message = _next_of_type(ws, "security_status")

    assert message["active"] is False
    assert "last_scan_at" not in message
    assert "latest_summary" not in message


def test_websocket_pushes_system_load(client) -> None:
    """Le HUD Godot attend cpu/ram/gpu sans avoir à les demander."""
    with client.websocket_connect("/ws") as ws:
        message = _next_of_type(ws, "system")

    assert set(message) == {"type", "cpu", "ram", "gpu", "source_agent"}


def test_websocket_chat_cycle(client, fake_core) -> None:
    """Le cycle attendu par Godot : thinking → speaking → idle."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "bonjour"})

        states = []
        answer = None
        for _ in range(15):
            message = ws.receive_json()
            if message.get("type") == "avatar_state":
                states.append(message["state"])
                if message["state"] == "speaking":
                    answer = message.get("text", "")
            if states[-3:] == ["thinking", "speaking", "idle"]:
                break

    assert states[-3:] == ["thinking", "speaking", "idle"]
    assert answer is not None, "aucun message 'speaking' recu"
    assert "bonjour" in answer


def test_websocket_pc_client_screen_question_still_captures(client, fake_core) -> None:
    """
    Comportement historique, inchangé : sans "hello" (ou avec un client
    autre que la PWA), une question écran reste autorisée — c'est le cas
    de Godot, toujours sur ce PC.
    """
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "regarde mon écran"})

        states = []
        for _ in range(15):
            message = ws.receive_json()
            if message.get("type") == "avatar_state":
                states.append(message["state"])
            if states[-3:] == ["watching", "speaking", "idle"]:
                break

    assert states[-3:] == ["watching", "speaking", "idle"]
    assert fake_core["asked_allow_screen_capture"] is True


def test_websocket_mobile_ambiguous_screen_question_does_not_watch(client, fake_core) -> None:
    """
    Bug trouvé par Cyril en test réel (02/08/2026) : la PWA envoyait la
    même question qu'un client PC et déclenchait la même capture. Le
    client s'annonce d'abord via "hello" — comme le fait réellement
    static/js/websocket.js.
    """
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "hello", "client": "lucas_pwa", "version": "1.0"})
        _next_of_type(ws, "chat")  # accusé de réception du hello

        ws.send_json({"type": "chat", "message": "que peux-tu voir sur mes écrans ?"})

        states = []
        for _ in range(15):
            message = ws.receive_json()
            if message.get("type") == "avatar_state":
                states.append(message["state"])
            if states[-3:] == ["thinking", "speaking", "idle"]:
                break

    assert states[-3:] == ["thinking", "speaking", "idle"]
    assert fake_core["asked_allow_screen_capture"] is False


def test_websocket_mobile_explicit_pc_mention_still_watches(
    client, fake_core, monkeypatch
) -> None:
    """
    Demande de Cyril (02/08/2026) : nommer le PC sans ambiguïté doit
    lever la restriction, même depuis la PWA — WATCHING doit refléter la
    VRAIE capture (décidée dans LucasCore), pas seulement le client.

    ⚠️ `classify` est neutralisé depuis le 05/08/2026. Ce test était
    INSTABLE : `should_use_vision()` délègue au classifieur d'intention,
    donc à Ollama. Il échouait ou passait selon l'état du serveur de
    modèles au moment de la campagne — observé en échec puis en succès la
    même nuit, sans qu'une ligne de code ait changé entre les deux.

    Un test rouge par intermittence est pire qu'un test absent : on
    apprend à l'ignorer, et il ne protège plus rien. Ce qu'il DOIT
    vérifier est déterministe — que `mentions_pc_explicitly()` lève bien
    la restriction mobile. Le classifieur est donc figé sur la réponse
    qu'il est censé donner ici, et sa propre justesse est mesurée là où
    c'est sa place : `test_intent.py`, sur un corpus dédié.
    """
    class _Intention:
        needs_screen = True
        needs_documents = False

    monkeypatch.setattr("core.intent.classify", lambda text, context="": _Intention())

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "hello", "client": "lucas_pwa", "version": "1.0"})
        _next_of_type(ws, "chat")

        ws.send_json({"type": "chat", "message": "regarde l'écran de mon PC"})

        states = []
        for _ in range(15):
            message = ws.receive_json()
            if message.get("type") == "avatar_state":
                states.append(message["state"])
            if states[-3:] == ["watching", "speaking", "idle"]:
                break

    assert states[-3:] == ["watching", "speaking", "idle"]
    # allow_screen_capture reste False (client mobile) : c'est
    # mentions_pc_explicitly(), à l'intérieur de LucasCore, qui lève la
    # restriction — pas ce indicateur-ci.
    assert fake_core["asked_allow_screen_capture"] is False


def test_websocket_ignores_an_unrecognized_message_type(client, fake_core) -> None:
    """Un type de message inconnu (else: continue) ne doit ni casser la connexion ni bloquer les suivants."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "morse_inconnu", "message": "..."})
        ws.send_json({"type": "chat", "message": "bonjour"})

        states = []
        for _ in range(15):
            message = ws.receive_json()
            if message.get("type") == "avatar_state":
                states.append(message["state"])
            if states[-3:] == ["thinking", "speaking", "idle"]:
                break

    assert states[-3:] == ["thinking", "speaking", "idle"]


def test_websocket_a_vision_check_failure_falls_back_to_thinking(client, fake_core, monkeypatch) -> None:
    """
    Un doute sur should_use_vision() (ou recent_context()) ne doit jamais
    empêcher de répondre — regarde=False, comme si l'écran n'était pas
    demandé, jamais une connexion rompue.
    """
    from api import server

    def _raise(message, context=""):
        raise RuntimeError("classifieur indisponible")

    monkeypatch.setattr(server, "should_use_vision", _raise)

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "regarde mon écran"})

        states = []
        for _ in range(15):
            message = ws.receive_json()
            if message.get("type") == "avatar_state":
                states.append(message["state"])
            if states[-3:] == ["thinking", "speaking", "idle"]:
                break

    assert states[-3:] == ["thinking", "speaking", "idle"], "jamais WATCHING quand le classifieur a échoué"


def test_websocket_also_emits_a_chat_message(client, fake_core) -> None:
    """
    Deux messages pour une réponse : l'état pilote l'animation du visage,
    le message de chat alimente la bulle du HUD.
    """
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "bonjour"})
        message = _next_of_type(ws, "chat")

    assert message["from_lucas"] is True
    assert "bonjour" in message["text"]


def test_websocket_relays_the_activity_events(client, fake_core) -> None:
    """
    Console de flux (IDEAS.md #77). _FakeCore émet deux événements
    pendant ask() (voir la fixture) : le serveur doit les relayer tels
    quels, dans l'ordre, avant la réponse — pas les inventer lui-même.
    """
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "bonjour"})

        events = []
        for _ in range(15):
            message = ws.receive_json()
            if message.get("type") == "activity":
                events.append((message["kind"], message["text"]))
            if message.get("type") == "chat":
                break

    assert events == [
        ("routed", "question reçue — traitée en LOCAL (fake)"),
        ("answered", "réponse prête (0.0 s)"),
    ]


def test_websocket_activity_events_arrive_before_the_answer(client, fake_core) -> None:
    """
    Point d'ordre : les événements décrivent ce qui a mené à la réponse,
    ils doivent donc arriver avant elle, pas après ou entremêlés au
    hasard de l'ordonnancement asyncio.
    """
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "bonjour"})

        types_in_order = []
        for _ in range(15):
            message = ws.receive_json()
            if message.get("type") in ("activity", "chat"):
                types_in_order.append(message["type"])
            if message.get("type") == "chat":
                break

    assert types_in_order == ["activity", "activity", "chat"]


def test_websocket_no_activity_events_when_the_core_emits_none(client, monkeypatch) -> None:
    """
    Une session sans callback (ou qui n'appelle jamais on_activity) ne
    doit produire aucun message « activity » fantôme — le serveur relaie,
    il n'invente rien.
    """
    class _SilentCore:
        def ask(self, message, image_path=None, allow_screen_capture=True, on_activity=None):
            return "réponse"

        def recent_context(self):
            return ""

        def close(self):
            pass

    monkeypatch.setattr("api.server.LucasCore", _SilentCore)

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "bonjour"})

        seen_types = []
        for _ in range(15):
            message = ws.receive_json()
            seen_types.append(message.get("type"))
            if message.get("type") == "chat":
                break

    assert "activity" not in seen_types


def test_websocket_accepts_the_godot_text_field(client, fake_core) -> None:
    """Le client Godot envoie « text » là où l'API attendait « message »."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "text": "depuis godot"})
        message = _next_of_type(ws, "chat")

    assert "depuis godot" in message["text"]


def test_websocket_answers_the_godot_handshake(client) -> None:
    """websocket_client.gd envoie « hello » dès la connexion."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "hello", "client": "lucas3d_godot"})
        message = _next_of_type(ws, "chat")

    assert "connectée" in message["text"]


def test_websocket_ignores_an_empty_message(client, fake_core) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "  "})
        ws.send_json({"type": "chat", "message": "vrai message"})
        assert _next_of_type(ws, "avatar_state", limit=20)["state"] in {"idle", "thinking"}


# ── WebSocket audio : aucun silence, jamais ────────────────────────────
#
# ⚠️ Deux silences réels trouvés le 05/08/2026 sur le chemin le plus
# utilisé par Cyril (bouton micro de la PWA) :
#
#   1. transcription VIDE -> retour à IDLE sans un mot. Il appuyait,
#      parlait, et rien ne se passait — indiscernable d'un bouton cassé.
#      C'est exactement ce qui arrive quand la voix est trop faible pour
#      Whisper : la transcription RÉUSSIT et rend une chaîne vide. C'est
#      donc la version dégradée du bug qu'il a rapporté (« je dois parler
#      fort »), et la plus déroutante des deux.
#   2. toute panne AUTRE que STTUnavailable remontait hors du handler et
#      FERMAIT la connexion. Côté PWA : bandeau qui clignote, reconnexion,
#      phrase perdue — une panne déguisée en hoquet réseau.
#
# Même doctrine que les blocs de contexte du prompt (ROADMAP.md §5.39) :
# une capacité qui ne produit rien doit le DIRE.


def _echange_audio(client, fake_stt, texte=None, boom=None, duree=1.5, confiance=0.9):
    """Envoie un audio et collecte ce que le serveur répond jusqu'à IDLE."""
    from modules.stt_engine import TranscriptResult

    double = fake_stt["_double"]
    if boom is not None:
        double.boom = boom
    else:
        double.boom = None
        double.transcribe_base64 = lambda audio_base64, suffix=".wav": TranscriptResult(
            text=texte, language="fr", confidence=confiance, duration_seconds=duree,
        )

    recus = []
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "hello", "client": "lucas_pwa", "version": "1.0"})
        # ⚠️ `audio_base64`, PAS `audio`. Le protocole n'accepte que ce
        # nom-là (api/protocol.py::read_user_audio, qui le documente :
        # « pas de deuxième nom accepté ici »). Avec la mauvaise clé, le
        # serveur fait simplement `continue` — mes premiers tests
        # échouaient donc sans que rien n'atteigne jamais le code testé.
        ws.send_json({"type": "audio", "audio_base64": "ZmF1eC1hdWRpbw=="})
        # Le serveur pousse en continu des messages `system` et
        # `security_status` en tâche de fond : on ignore tout ce qui n'est
        # pas une réponse à CET envoi, plutôt que de compter des positions.
        pertinents = ("error", "chat", "avatar_state", "activity", "speech")
        for _ in range(30):
            message = ws.receive_json()
            if message.get("type") not in pertinents:
                continue
            recus.append(message)
            if (
                message.get("type") == "avatar_state"
                and message.get("state") == "idle"
                and len(recus) > 1
            ):
                break
    return recus


def test_an_empty_transcription_is_reported_not_swallowed(client, fake_core, fake_stt) -> None:
    """LE cas du bug micro : Whisper réussit et rend une chaîne vide."""
    recus = _echange_audio(client, fake_stt, texte="")
    erreurs = [m for m in recus if m.get("type") == "error"]
    assert erreurs, "un micro qui n'entend rien doit le dire"
    # `detail`, pas `message` — c'est le nom du champ dans protocol.error().
    assert "plus fort" in erreurs[0].get("detail", "").lower()


def test_an_empty_transcription_reports_the_measured_duration(client, fake_core, fake_stt) -> None:
    """
    La durée détectée distingue deux pannes très différentes : « 0,1 s
    reçues » désigne l'enregistrement côté client, « 3,2 s reçues mais
    rien reconnu » désigne le niveau sonore. Sans elle, on cherche à
    l'aveugle — et c'est précisément le diagnostic ouvert sur le micro.
    """
    recus = _echange_audio(client, fake_stt, texte="", duree=3.2)
    assert any(
        m.get("type") == "activity" and "3.2s" in str(m) and "aucune parole" in str(m)
        for m in recus
    )


def test_whitespace_only_counts_as_empty(client, fake_core, fake_stt) -> None:
    """
    Whisper rend volontiers un espace ou un saut de ligne sur du silence.
    Sans `.strip()`, cette chaîne passait pour une vraie question et
    partait au LLM — qui répondait à du vide.
    """
    recus = _echange_audio(client, fake_stt, texte="\n  ")
    assert any(m.get("type") == "error" for m in recus)


def test_an_unexpected_failure_does_not_kill_the_connection(client, fake_core, fake_stt) -> None:
    """
    Seul STTUnavailable était rattrapé. Une panne de décodeur fermait la
    connexion, et la PWA se reconnectait en silence — indiscernable d'un
    problème de réseau.
    """
    recus = _echange_audio(client, fake_stt, boom=MemoryError("plus de mémoire"))
    erreurs = [m for m in recus if m.get("type") == "error"]
    assert erreurs, "la panne doit être annoncée, pas fermer la connexion"
    assert "MemoryError" in erreurs[0].get("detail", "")


def test_the_avatar_returns_to_idle_after_a_silent_recording(client, fake_core, fake_stt) -> None:
    """
    Un avatar bloqué sur « listening » laisserait croire que Luca écoute
    encore, alors qu'elle a déjà abandonné.
    """
    recus = _echange_audio(client, fake_stt, texte="")
    etats = [m.get("state") for m in recus if m.get("type") == "avatar_state"]
    assert etats and etats[-1] == "idle"


def test_a_real_transcription_still_goes_through(client, fake_core, fake_stt) -> None:
    """Garde-fou : ces correctifs ne doivent pas avaler un enregistrement valide."""
    recus = _echange_audio(client, fake_stt, texte="quelle heure est-il")
    assert not [m for m in recus if m.get("type") == "error"]




def test_a_low_confidence_hallucination_is_rejected(client, fake_core, fake_stt) -> None:
    """
    ⚠️ CE test vient du REEL, pas de l'imagination — et il montre pourquoi
    les tests unitaires seuls ne suffisaient pas.

    Le premier correctif ne testait que la chaîne vide, et tous les tests
    passaient. Confronté au vrai moteur Whisper sur un WAV de silence
    pur :

        silence 2 s   -> texte 'You',    confiance 0,349
        silence 3 s   -> texte 'You',    confiance 0,305
        parole réelle -> texte juste,    confiance 0,995

    Whisper HALLUCINE un mot court et plausible. Ce mot partait au LLM,
    qui répondait à du vide — observé tel quel avant ce correctif.

    La confiance sépare les deux cas sans ambiguïté, et `is_confident`
    existait déjà dans TranscriptResult : simplement jamais consulté.
    """
    recus = _echange_audio(client, fake_stt, texte="You", confiance=0.35)
    erreurs = [m for m in recus if m.get("type") == "error"]
    assert erreurs, "une hallucination à faible confiance ne doit pas partir au LLM"
    assert "plus fort" in erreurs[0].get("detail", "").lower()


def test_the_reported_confidence_helps_diagnosis(client, fake_core, fake_stt) -> None:
    """
    Distinguer « 0,3 de confiance » de « 0 s reçues » oriente vers deux
    causes opposées : niveau sonore trop faible, ou enregistrement vide
    côté client. Le diagnostic micro est encore ouvert.
    """
    recus = _echange_audio(client, fake_stt, texte="You", confiance=0.35, duree=2.0)
    assert any(
        m.get("type") == "activity" and "0.35" in str(m) for m in recus
    )


def test_a_confident_transcription_is_not_rejected(client, fake_core, fake_stt) -> None:
    """
    Garde-fou symétrique : le seuil ne doit pas avaler une vraie phrase.
    Une parole réelle mesure 0,97-0,99, très au-dessus du seuil de 0,6.
    """
    recus = _echange_audio(client, fake_stt, texte="ouvre le bloc note", confiance=0.97)
    assert not [m for m in recus if m.get("type") == "error"]


# ── WebSocket : audio (pont mobile, Phase 4) ───────────────────────────
#
# Premier appelant réel de modules/stt_engine.py — jusqu'ici écrit et
# testé, mais rien ne l'alimentait (voir son en-tête). Ces tests
# vérifient le CHEMIN serveur, pas la qualité de la transcription : le
# moteur STT est entièrement doublé.

def test_websocket_audio_is_transcribed_and_answered(client, fake_core, fake_stt) -> None:
    """Le cycle attendu : listening → thinking → speaking → idle."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "audio", "audio_base64": "ZmF1eCBhdWRpbw=="})

        states = []
        answer = None
        for _ in range(20):
            message = ws.receive_json()
            if message.get("type") == "avatar_state":
                states.append(message["state"])
                if message["state"] == "speaking":
                    answer = message.get("text", "")
            if states[-4:] == ["listening", "thinking", "speaking", "idle"]:
                break

    assert states[-4:] == ["listening", "thinking", "speaking", "idle"]
    # fake_core renvoie "réponse à « <message demandé> »" — le message
    # demandé doit être le texte transcrit, pas l'audio brut.
    assert answer is not None, "aucun message 'speaking' recu"
    assert "audio transcrit" in answer


def test_websocket_audio_reports_detected_duration_for_diagnosis(client, fake_core, fake_stt) -> None:
    """
    Instrumentation ajoutée le 05/08/2026 (bug micro remonté par Cyril,
    cause non confirmée) : la durée détectée par Whisper doit être
    communiquée au client, pour comparaison avec la durée mesurée côté
    navigateur au prochain test réel.
    """
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "audio", "audio_base64": "ZmF1eCBhdWRpbw=="})

        activity_texts = []
        states = []
        for _ in range(20):
            message = ws.receive_json()
            if message.get("type") == "activity":
                activity_texts.append(message.get("text", ""))
            if message.get("type") == "avatar_state":
                states.append(message["state"])
                # Un "idle" est déjà envoyé juste après la connexion, avant
                # tout traitement (voir websocket_endpoint()) — attendre la
                # VRAIE séquence complète, pas le premier idle venu.
                if states[-4:] == ["listening", "thinking", "speaking", "idle"]:
                    break

    assert any("1.5s détectées" in t and "15 caractère" in t for t in activity_texts)


def test_websocket_audio_reaches_the_stt_engine(client, fake_core, fake_stt) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "audio", "audio_base64": "ZmF1eCBhdWRpbw=="})
        _next_of_type(ws, "chat")

    assert fake_stt["audio_base64"] == "ZmF1eCBhdWRpbw=="


def test_websocket_audio_transcript_is_asked_to_lucas(client, fake_core, fake_stt) -> None:
    """Le transcrit doit suivre EXACTEMENT le même chemin qu'un message tapé."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "audio", "audio_base64": "ZmF1eCBhdWRpbw=="})
        _next_of_type(ws, "chat")

    assert fake_core.get("asked") == "audio transcrit"


def test_websocket_ignores_audio_without_the_field(client, fake_core, fake_stt) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "audio"})
        ws.send_json({"type": "chat", "message": "vrai message"})
        message = _next_of_type(ws, "chat", limit=20)

    assert "vrai message" in message["text"]
    assert "audio_base64" not in fake_stt


def test_websocket_stt_unavailable_reports_an_error_not_a_crash(client, fake_core, fake_stt) -> None:
    """
    Un doute sur l'audio ne doit jamais planter la connexion — mais
    contrairement au chemin vision, Cyril doit savoir qu'on ne l'a pas
    entendu : un silence serait plus trompeur qu'un message d'erreur.
    """
    fake_stt["_double"].boom = fake_stt["_STTUnavailable"]("aucun backend Whisper")

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "audio", "audio_base64": "ZmF1eCBhdWRpbw=="})
        error = _next_of_type(ws, "error")
        idle = _next_of_type(ws, "avatar_state")

    assert "Whisper" in error["detail"]
    assert idle["state"] == "idle"


def test_websocket_silence_returns_to_idle_without_asking_lucas(client, fake_core, fake_stt) -> None:
    """
    Un extrait sans parole (texte transcrit vide) ne doit pas devenir une
    question vide envoyée à LucasCore.ask().
    """
    fake_stt["_double"].texte = ""

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "audio", "audio_base64": "ZmF1eCBhdWRpbw=="})
        ws.send_json({"type": "chat", "message": "toujours vivant"})
        message = _next_of_type(ws, "chat", limit=20)

    assert "toujours vivant" in message["text"]
    assert "asked" not in fake_core or fake_core["asked"] != ""


# ── Voix (pont mobile TTS) ──────────────────────────────────────────────
#
# Optionnelle : la vaste majorité des tests ci-dessus n'envoient jamais
# "speak", donc ce chemin n'est même pas emprunté — vérifié explicitement
# ici (première fonction) pour que ce ne soit pas juste une supposition.

def test_websocket_sends_no_speech_without_the_speak_flag(client, fake_core, fake_voice) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "bonjour"})

        types_seen = []
        for _ in range(15):
            message = ws.receive_json()
            types_seen.append(message.get("type"))
            if message.get("type") == "chat":
                break

    assert "speech" not in types_seen
    assert fake_voice.get("text") is None, "synthesize_routed() n'a pas dû être appelé"


def test_websocket_sends_speech_when_requested(client, fake_core, fake_voice) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "bonjour", "speak": True})
        speech = _next_of_type(ws, "speech", limit=20)

    assert speech["mime"] == "audio/mpeg"  # le double rend un chemin .mp3
    assert base64.b64decode(speech["audio_base64"]) == b"FAKE-MP3-BYTES"
    # Le texte routé doit être la RÉPONSE (fake_core la préfixe « réponse
    # à « ... » »), la question sert au routage — route_voice() regarde
    # les deux (voir modules/voice_manager.py).
    assert "bonjour" in fake_voice["text"] and fake_voice["text"] != "bonjour"
    assert fake_voice["question"] == "bonjour"


def test_websocket_reports_a_synthesized_voice_as_an_activity(client, fake_core, fake_voice) -> None:
    """
    Console de flux (IDEAS.md #77) : la voix est un fait à afficher,
    comme le reste. ⚠️ Cet événement arrive APRÈS « chat » dans le flux
    (le texte part d'abord, la synthèse ensuite) — attendre le idle qui
    SUIT le chat, pas le idle initial de connexion (déjà en file
    d'attente avant même l'envoi du message).
    """
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "bonjour", "speak": True})

        types_seen, activity_texts = [], []
        for _ in range(20):
            message = ws.receive_json()
            types_seen.append(message.get("type"))
            if message.get("type") == "activity":
                activity_texts.append(message["text"])
            if (
                message.get("type") == "avatar_state"
                and message.get("state") == "idle"
                and "chat" in types_seen
            ):
                break

    assert any("voix synthétisée" in text and "mpeg" in text for text in activity_texts)


def test_websocket_reports_declined_speech_plainly(client, fake_core, monkeypatch) -> None:
    """
    synthesize_routed() rend None sur contenu sensible + voix locale
    indisponible (modules/voice_manager.py) — jamais un silence côté
    PWA : Cyril doit savoir que la voix a été sciemment coupée.
    """
    class _DecliningVoiceManager:
        def synthesize_routed(self, text, question=""):
            return None

    monkeypatch.setattr("api.server._voice_manager", _DecliningVoiceManager())

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "mon salaire", "speak": True})

        types_seen, activity_texts = [], []
        for _ in range(20):
            message = ws.receive_json()
            types_seen.append(message.get("type"))
            if message.get("type") == "activity":
                activity_texts.append(message["text"])
            if (
                message.get("type") == "avatar_state"
                and message.get("state") == "idle"
                and "chat" in types_seen
            ):
                break

    assert "speech" not in types_seen
    assert any("non prononcée" in text for text in activity_texts)


def test_websocket_a_tts_crash_does_not_break_the_text_answer(client, fake_core, monkeypatch) -> None:
    """
    Une panne de synthèse (edge_tts hors ligne, par ex.) ne doit jamais
    invalider une réponse texte déjà prête — même garde que pour la
    vision et l'audio ailleurs dans ce fichier.
    """
    class _CrashingVoiceManager:
        def synthesize_routed(self, text, question=""):
            raise RuntimeError("réseau indisponible")

    monkeypatch.setattr("api.server._voice_manager", _CrashingVoiceManager())

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "bonjour", "speak": True})

        types_seen, activity_texts = [], []
        for _ in range(20):
            message = ws.receive_json()
            types_seen.append(message.get("type"))
            if message.get("type") == "activity":
                activity_texts.append(message["text"])
            if message.get("type") == "avatar_state" and message.get("state") == "idle" and "chat" in types_seen:
                break

    assert "chat" in types_seen, "la réponse texte doit partir malgré la panne TTS"
    assert "speech" not in types_seen
    assert any("voix indisponible" in text for text in activity_texts)
    assert types_seen[-1] == "avatar_state", "la connexion doit terminer proprement, pas planter"


def test_websocket_speech_mime_matches_wav_for_piper(client, fake_core, monkeypatch, tmp_path) -> None:
    audio_path = tmp_path / "output_piper.wav"
    audio_path.write_bytes(b"FAKE-WAV-BYTES")

    class _PiperVoiceManager:
        def synthesize_routed(self, text, question=""):
            return str(audio_path)

    monkeypatch.setattr("api.server._voice_manager", _PiperVoiceManager())

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "message": "bonjour", "speak": True})
        speech = _next_of_type(ws, "speech", limit=20)

    assert speech["mime"] == "audio/wav"


def test_websocket_image_reply_can_also_be_spoken(client, fake_core, fake_voice) -> None:
    """La voix ne doit pas être réservée au texte tapé — même mécanisme partout."""
    image_b64 = base64.b64encode(b"donnees-image-factices").decode()

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "image", "image_base64": image_b64, "speak": True})
        speech = _next_of_type(ws, "speech", limit=20)

    assert base64.b64decode(speech["audio_base64"]) == b"FAKE-MP3-BYTES"


def test_websocket_audio_transcript_reply_can_also_be_spoken(client, fake_core, fake_stt, fake_voice) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "audio", "audio_base64": "ZmF1eCBhdWRpbw==", "speak": True})
        speech = _next_of_type(ws, "speech", limit=20)

    assert base64.b64decode(speech["audio_base64"]) == b"FAKE-MP3-BYTES"
    assert fake_voice["question"] == "audio transcrit"


# ── Jeton API (prérequis pont mobile) ──────────────────────────────────
#
# API_TOKEN est vide par défaut (config.py) : ces tests forcent une
# valeur pour vérifier le mécanisme, mais le comportement PAR DÉFAUT —
# testé partout ailleurs dans ce fichier, sans jeton — ne doit jamais
# changer tant que Cyril n'a rien renseigné dans .env.

def test_status_never_requires_a_token(client, monkeypatch) -> None:
    """Ping de santé — rien de sensible, ouvert même quand un jeton existe."""
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    assert client.get("/status").status_code == 200


def test_chat_without_token_is_rejected_once_one_is_set(client, fake_core, monkeypatch) -> None:
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    response = client.post("/chat", json={"message": "test"})
    assert response.status_code == 401


def test_chat_with_the_wrong_token_is_rejected(client, fake_core, monkeypatch) -> None:
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    response = client.post(
        "/chat",
        json={"message": "test"},
        headers={"Authorization": "Bearer mauvais-jeton"},
    )
    assert response.status_code == 401


def test_chat_with_the_right_token_succeeds(client, fake_core, monkeypatch) -> None:
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    response = client.post(
        "/chat",
        json={"message": "test"},
        headers={"Authorization": "Bearer secret123"},
    )
    assert response.status_code == 200


def test_history_and_system_also_require_the_token(client, fake_core, monkeypatch) -> None:
    """
    Pas seulement /chat : /history (tout l'historique) et /system (titre
    de fenêtre active, aussi révélateur qu'un nom de fichier ouvert)
    exposent chacun quelque chose de sensible.
    """
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    assert client.get("/history").status_code == 401
    assert client.get("/system").status_code == 401


def test_no_token_configured_means_no_token_required(client, fake_core) -> None:
    """
    Le comportement par défaut, sans API_TOKEN dans .env : identique à
    avant que ce mécanisme existe. Aucune régression pour Cyril tant
    qu'il n'a rien renseigné.
    """
    assert client.post("/chat", json={"message": "test"}).status_code == 200
    assert client.get("/history").status_code == 200
    assert client.get("/system").status_code == 200


def test_websocket_without_token_is_closed_once_one_is_set(client, monkeypatch) -> None:
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws") as ws:
        ws.receive_json()


def test_websocket_with_the_right_token_in_the_query_string_succeeds(client, monkeypatch) -> None:
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    with client.websocket_connect("/ws?token=secret123") as ws:
        first = _next_of_type(ws, "avatar_state")
    assert first["state"] == "idle"


def test_websocket_without_token_configured_still_works(client) -> None:
    """Comportement par défaut, jeton non configuré : inchangé."""
    with client.websocket_connect("/ws") as ws:
        first = _next_of_type(ws, "avatar_state")
    assert first["state"] == "idle"


# ── WebSocket : jeton par sous-protocole (hors des logs) ───────────────
#
# Le jeton passait en clair dans data/logs/server_startup.log, uvicorn
# journalisant la query string. Il voyage désormais dans l'en-tête
# Sec-WebSocket-Protocol, que rien ne journalise. La query string reste
# acceptée en repli — d'où les tests des DEUX chemins ci-dessous.


def test_websocket_with_the_right_token_in_a_subprotocol_succeeds(client, monkeypatch) -> None:
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    with client.websocket_connect(
        "/ws", subprotocols=["lucas.v1", "lucas-token.secret123"]
    ) as ws:
        first = _next_of_type(ws, "avatar_state")
    assert first["state"] == "idle"


def test_websocket_with_a_wrong_token_in_a_subprotocol_is_closed(client, monkeypatch) -> None:
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    with pytest.raises(WebSocketDisconnect), client.websocket_connect(
        "/ws", subprotocols=["lucas.v1", "lucas-token.mauvais"]
    ) as ws:
        ws.receive_json()


def test_subprotocol_token_wins_over_the_query_string(client, monkeypatch) -> None:
    """
    Le sous-protocole est consulté en premier : un client à jour n'échoue
    pas parce qu'une vieille query string traîne dans son URL. Le cas
    inverse (query string valide, sous-protocole faux) doit échouer — sans
    quoi le repli deviendrait un contournement du contrôle.
    """
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    with pytest.raises(WebSocketDisconnect), client.websocket_connect(
        "/ws?token=secret123", subprotocols=["lucas.v1", "lucas-token.mauvais"]
    ) as ws:
        ws.receive_json()


def test_server_echoes_only_the_protocol_never_the_token(client, monkeypatch) -> None:
    """
    Le sous-protocole porteur du jeton ne doit jamais revenir au client :
    il serait alors visible dans l'en-tête de RÉPONSE, et donc renvoyé au
    point de départ. Seul `lucas.v1` est négocié.
    """
    monkeypatch.setattr("api.server.API_TOKEN", "secret123")
    with client.websocket_connect(
        "/ws", subprotocols=["lucas.v1", "lucas-token.secret123"]
    ) as ws:
        _next_of_type(ws, "avatar_state")
        accepte = ws.scope.get("subprotocol") if hasattr(ws, "scope") else None
    assert accepte in (None, "lucas.v1")


def test_websocket_accepts_a_client_that_proposes_no_subprotocol(client) -> None:
    """
    Godot, curl et les tests historiques n'annoncent aucun sous-protocole.
    Renvoyer `lucas.v1` à un client qui ne l'a pas proposé ferait fermer la
    connexion par un navigateur — le serveur ne sélectionne donc rien.
    """
    with client.websocket_connect("/ws") as ws:
        first = _next_of_type(ws, "avatar_state")
    assert first["state"] == "idle"


# ── WebSocket : image (pont mobile, Phase 4) ───────────────────────────
#
# Photo envoyée par le téléphone (pas de caméra sur le PC — voir
# VISION_LONG_TERME.md §2 Pilier 3). LucasCore est doublé (fake_core) :
# ces tests vérifient le CHEMIN serveur — décodage, témoin WATCHING,
# nettoyage du fichier temporaire — pas la qualité de l'OCR/VLM, qui a
# ses propres tests dans test_vision_routing.py.

FAKE_IMAGE_B64 = base64.b64encode(b"fausses donnees d'image, jamais un vrai jpeg").decode()


def test_websocket_image_is_analyzed_and_answered(client, fake_core) -> None:
    """Le cycle attendu : watching → speaking → idle, pas listening (audio only)."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "image", "image_base64": FAKE_IMAGE_B64})

        states = []
        answer = None
        for _ in range(20):
            message = ws.receive_json()
            if message.get("type") == "avatar_state":
                states.append(message["state"])
                if message["state"] == "speaking":
                    answer = message.get("text", "")
            if states[-3:] == ["watching", "speaking", "idle"]:
                break

    assert states[-3:] == ["watching", "speaking", "idle"]
    assert answer is not None


def test_websocket_image_without_caption_uses_a_default(client, fake_core) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "image", "image_base64": FAKE_IMAGE_B64})
        _next_of_type(ws, "chat")

    assert fake_core["asked"] == "Décris ce que tu vois."


def test_websocket_image_with_a_caption_uses_it(client, fake_core) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json(
            {"type": "image", "image_base64": FAKE_IMAGE_B64, "text": "c'est quoi ce panneau ?"}
        )
        _next_of_type(ws, "chat")

    assert fake_core["asked"] == "c'est quoi ce panneau ?"


def test_websocket_image_reaches_lucas_core_with_a_real_path(client, fake_core) -> None:
    """
    Le fichier temporaire doit exister PENDANT l'appel — c'est de là que
    LucasCore._describe_camera_image() lit l'image.
    """
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "image", "image_base64": FAKE_IMAGE_B64})
        _next_of_type(ws, "chat")

    assert fake_core["asked_image_path"] is not None
    assert fake_core["image_existed_during_call"] is True


def test_websocket_image_temp_file_is_deleted_after_use(client, fake_core) -> None:
    """
    Ce sont potentiellement des photos de documents personnels : elles ne
    doivent pas traîner dans le dossier temporaire du système au-delà de
    l'appel — même principe que pour les PDF scannés (memory/index_documents.py).
    """
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "image", "image_base64": FAKE_IMAGE_B64})
        _next_of_type(ws, "chat")

    path = fake_core["asked_image_path"]
    assert not os.path.exists(path)


def test_websocket_ignores_image_without_the_field(client, fake_core) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "image"})
        ws.send_json({"type": "chat", "message": "vrai message"})
        message = _next_of_type(ws, "chat", limit=20)

    assert "vrai message" in message["text"]


def test_websocket_bad_base64_image_reports_an_error_not_a_crash(client, fake_core) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "image", "image_base64": "!!! pas du base64 valide !!!"})
        error = _next_of_type(ws, "error")
        idle = _next_of_type(ws, "avatar_state")

    assert "Image illisible" in error["detail"]
    assert idle["state"] == "idle"


# ── PWA statique ────────────────────────────────────────────────────────

def test_pwa_index_is_served(client) -> None:
    response = client.get("/app/")
    assert response.status_code == 200
    assert "manifest.json" in response.text


def test_pwa_manifest_is_served(client) -> None:
    response = client.get("/app/manifest.json")
    assert response.status_code == 200
    assert response.json()["name"] == "Luca's"


def test_pwa_does_not_shadow_the_json_api(client) -> None:
    """Le mount /app est déclaré en dernier : les routes JSON doivent rester atteignables."""
    assert client.get("/status").status_code == 200


# ── Cohérence avec le reste du projet ─────────────────────────────────

def test_world_model_is_not_reimplemented() -> None:
    """
    core/world_model.py affirme dans son en-tête avoir centralisé ce code.
    api/server.py en gardait pourtant une copie : deux implémentations
    qui pouvaient diverger sans que rien ne le signale.
    """
    source = (
        __import__("pathlib").Path("api/server.py").read_text(encoding="utf-8")
    )
    assert "_get_active_window_title" not in source
    assert "get_snapshot" in source


# ── Boucles de fond du WebSocket (jamais appelées directement ailleurs) ─

def test_push_system_state_stops_on_a_broken_connection() -> None:
    """
    _push_system_state() tourne en boucle infinie pour le HUD Godot —
    la seule façon d'en sortir est l'exception attrapée. Sans elle, une
    déconnexion laisserait la tâche de fond tourner pour rien.
    """
    import asyncio

    from api.server import _push_system_state

    class _BrokenWebSocket:
        async def send_json(self, data):
            raise RuntimeError("connexion fermée")

    # `_BrokenWebSocket` n'implemente que `send_json` — c'est tout ce
    # que la fonction utilise. Substitution volontaire, invisible a mypy.
    asyncio.run(_push_system_state(_BrokenWebSocket()))  # type: ignore[arg-type]  # ne doit jamais lever ni boucler


def test_push_security_status_stops_on_a_broken_connection() -> None:
    import asyncio

    from api.server import _push_security_status

    class _BrokenWebSocket:
        async def send_json(self, data):
            raise RuntimeError("connexion fermée")

    asyncio.run(_push_security_status(_BrokenWebSocket()))  # type: ignore[arg-type]  # ne doit jamais lever ni boucler


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
