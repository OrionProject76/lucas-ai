# api/server.py — API FastAPI unique de Luca's
#
# Pourquoi une seule API (et pas un serveur séparé pour Godot) ?
# Un seul point de vérité, moins de code à maintenir en double.
# Le mobile (PWA) utilise les routes REST classiques ci-dessous.
# Godot utilisera plus tard l'endpoint WebSocket /ws (protocole minimal,
# voir VISION_LONG_TERME.md §2, Pilier 3 — le corps étendu PC + mobile).

import asyncio
import base64
import secrets
import sys
import tempfile
from pathlib import Path

# Permet de lancer ce fichier directement (uvicorn api.server:app depuis la racine)
# ou en important le module depuis un autre script, sans casser les imports relatifs.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api import log_scrub, protocol
from config import API_TOKEN
from core.lucas_core import LucasCore
from core.router import mentions_pc_explicitly, should_use_vision
from core.world_model import get_snapshot
from memory.memory_manager import save_event_from_any_thread
from modules.capability_registry import VERIFIED_AT as CAPABILITY_REGISTRY_VERIFIED_AT
from modules.capability_registry import list_capabilities
from modules.sandbox_manager import SandboxError
from modules.sandbox_manager import execute as sandbox_execute
from modules.sandbox_manager import reject as sandbox_reject
from modules.sandbox_manager import submit as sandbox_submit
from modules.semantic_desktop import SemanticDesktop
from modules.stt_engine import STTEngine, STTUnavailable
from modules.voice_manager import VoiceManager
from modules.workspace_manager import InvalidLayout
from modules.workspace_manager import get_layout as workspace_get_layout
from modules.workspace_manager import save_layout as workspace_save_layout
from modules.workspace_manager import summary as workspace_summary
from security.status import get_status as get_security_status

app = FastAPI(title="Luca's API", version="0.2")

# Masque tout `token=...` avant écriture dans les logs d'uvicorn. Posé ici,
# à l'import du module d'application, pour s'appliquer quel que soit le mode
# de lancement (uvicorn en CLI, tâche planifiée LucasAPIServer, tests) sans
# dépendre d'une option passée en ligne de commande, qu'on oublierait un
# jour. Voir api/log_scrub.py pour le détail.
log_scrub.install()

# Instance unique, partagée entre tous les messages « audio » du WebSocket.
# Contrairement à LucasCore (recréé par appel à cause de SQLite, voir plus
# bas), STTEngine ne touche à aucune base — le websocket est géré dans la
# boucle asyncio, un seul thread, donc pas de risque à la partager. La
# recréer par message rechargerait le modèle Whisper à chaque phrase.
_stt_engine = STTEngine()

# Même raisonnement pour la voix : PiperEngine met en cache son modèle
# (~60-75 Mo) au premier usage — le recréer par requête le rechargerait à
# chaque question routée en local. log_event branché sur la même table
# que le reste (save_event_from_any_thread) : les événements
# tts_skipped_sensitive / tts_cloud_on_sensitive doivent s'enregistrer
# pour le pont mobile exactement comme pour l'UI PySide6 (CLAUDE.md,
# section TTS) — pas un comportement réservé au bureau.
_voice_manager = VoiceManager(log_event=save_event_from_any_thread)

_AUDIO_MIME_TYPES = {".mp3": "audio/mpeg", ".wav": "audio/wav"}


def _read_audio_b64(path: str) -> str:
    """Read an audio file and return its base64 payload.

    Split out so the blocking read can run in a worker thread: called
    directly from the async WebSocket handler it would freeze the event
    loop — and therefore every other connection — for the duration of
    the read.
    """
    with open(path, "rb") as audio_file:
        return base64.b64encode(audio_file.read()).decode("ascii")


def _audio_mime_type(path: str) -> str:
    return _AUDIO_MIME_TYPES.get(Path(path).suffix.lower(), "application/octet-stream")

# ── CORS : resserré le 05/08/2026, une fois l'origine Tailscale connue ─
#
# Il était à `["*"]` avec la note « à restreindre une fois le PWA en
# place ». Le PWA est en place, et l'accès distant vient d'ouvrir.
#
# ⚠️ Ce que ce resserrage protège, et ce qu'il ne protège pas — la
# distinction compte, sinon on croit avoir fermé plus qu'on n'a fermé :
#
# - La PWA est SERVIE par ce serveur (`/app`). Ses appels sont donc en
#   MÊME ORIGINE, et CORS ne s'y applique pas du tout. Ce réglage ne
#   change rien à son fonctionnement.
# - Ce qu'il empêche : qu'une page web quelconque, ouverte dans le
#   navigateur de Cyril, appelle `GET /history` en JavaScript et lise
#   tout son historique de conversation. Avec `["*"]`, le navigateur
#   l'autorisait ; désormais il refuse.
# - Ce qu'il n'empêche PAS : un appel direct hors navigateur (curl, un
#   script). CORS est une protection du NAVIGATEUR, pas du serveur — la
#   barrière contre ça reste `API_TOKEN`, et elle seule.
#
# Les adresses viennent de ce que cette machine tient réellement
# (vérifié : `Get-NetIPAddress`), pas d'une supposition :
#   192.168.1.12    Ethernet, réservation DHCP Livebox
#   192.168.1.14    Wi-Fi du MÊME PC — active, et elle répond
#   100.88.249.117  Tailscale, accès distant
#
# ⚠️ `.14` n'est PAS l'adresse du téléphone, contrairement à ce qui avait
# été conclu le matin du 05/08 : c'est la seconde interface de ce PC. Le
# Wi-Fi était éteint au moment de ce diagnostic, d'où la confusion. La
# retirer couperait l'accès via cette interface.
_ORIGINES_AUTORISEES = [
    "https://192.168.1.12:8000",
    "https://192.168.1.14:8000",
    "https://100.88.249.117:8000",
    "https://127.0.0.1:8000",
    "https://localhost:8000",
    # HTTP pour `just serve-http` (dépannage local sans certificat).
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ORIGINES_AUTORISEES,
    # La spec CORS interdit credentials + origine « * » : les navigateurs
    # rejettent la combinaison. Reste False — le jeton voyage par en-tête
    # `Authorization`, jamais par cookie, donc rien à autoriser ici.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


class WorkspaceLayoutRequest(BaseModel):
    order: list[str]
    sizes: dict[str, str]


class SandboxSubmitRequest(BaseModel):
    code: str


# ── Jeton partagé (prérequis pour le pont mobile, ROADMAP.md §2) ───────
#
# Posé le 02/08/2026. Vide par défaut (config.py) désactive la
# vérification — mais ⚠️ CORRIGÉ le 07/08/2026 (audit du pont WebSocket
# Godot) : ce commentaire disait « SANS EFFET aujourd'hui », FAUX depuis
# qu'un vrai .env avec un vrai API_TOKEN existe (créé pour le pont
# mobile, ROADMAP.md §5.30). Vérifié le 07/08 : 43 caractères présents —
# la vérification est bien active, pas un no-op silencieux.


def _token_is_valid(fourni: str | None) -> bool:
    """
    Compare en temps constant (secrets.compare_digest) : une comparaison
    `==` classique sur une chaîne fuit sa longueur/son préfixe par le
    temps de réponse, un détail qui compte pour un jeton, pas pour le
    reste de cette API.
    """
    if not API_TOKEN:
        return True
    return fourni is not None and secrets.compare_digest(fourni, API_TOKEN)


# Sous-protocole WebSocket annoncé par la PWA, et préfixe du sous-protocole
# porteur du jeton. La PWA propose les deux : ["lucas.v1",
# "lucas-token.<jeton>"]. Le second est un véhicule, pas un protocole — il
# n'est jamais renvoyé au client.
#
# Les caractères autorisés dans un sous-protocole sont ceux d'un « token »
# HTTP (RFC 6455 §4.1, qui renvoie à la grammaire RFC 7230) : ni espace, ni
# guillemet, ni virgule. Les jetons produits par secrets.token_urlsafe (le
# cas normal) n'utilisent que [A-Za-z0-9_-], tous valides. Un jeton écrit à
# la main avec un caractère interdit rendrait la connexion impossible : le
# client le détecte et retombe sur la query string plutôt que d'échouer
# (voir static/js/websocket.js).
WS_SUBPROTOCOL = "lucas.v1"
WS_TOKEN_SUBPROTOCOL_PREFIX = "lucas-token."


def _token_from_subprotocols(websocket: WebSocket) -> str | None:
    """
    Extrait le jeton du sous-protocole `lucas-token.<jeton>`, s'il est là.

    Retourne None si aucun sous-protocole ne porte le préfixe — l'appelant
    retombe alors sur la query string. Distinguer None (« rien annoncé »)
    d'une chaîne vide (« annoncé, mais vide ») compte : la seconde est un
    jeton invalide, qui doit fermer la connexion, pas déclencher le repli.
    """
    for propose in websocket.scope.get("subprotocols") or []:
        if propose.startswith(WS_TOKEN_SUBPROTOCOL_PREFIX):
            return propose.removeprefix(WS_TOKEN_SUBPROTOCOL_PREFIX)
    return None


def verify_token(authorization: str | None = Header(default=None)) -> None:
    """
    Dépendance REST : `Authorization: Bearer <jeton>`.

    Lève 401 plutôt que 403 : le client ne sait pas s'il a le droit, il
    n'a simplement pas prouvé une identité — c'est la distinction que
    HTTP fait entre les deux codes.
    """
    fourni = None
    if authorization and authorization.startswith("Bearer "):
        fourni = authorization.removeprefix("Bearer ").strip()

    if not _token_is_valid(fourni):
        raise HTTPException(status_code=401, detail="Jeton API manquant ou invalide")


# ── Endpoints REST ──────────────────────────────────────────────

@app.get("/status")
def status():
    """Ping simple — confirme que le serveur tourne."""
    return {"status": "running", "version": "0.2"}


@app.post("/chat", dependencies=[Depends(verify_token)])
def chat(req: ChatRequest):
    """
    Envoie un message à Luca's et retourne sa réponse.

    Note technique : on crée une instance LucasCore par requête plutôt
    qu'une instance partagée au niveau du module. Raison : SQLite refuse
    par défaut d'être utilisé depuis un thread différent de celui qui a
    ouvert la connexion, et FastAPI traite chaque requête dans un thread
    du pool. Comme tout l'état (historique) vit dans la base SQLite et
    pas en mémoire Python, recréer LucasCore() à chaque appel est sans
    coût réel de logique — juste une micro-latence d'ouverture de fichier.
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message vide")

    lucas = LucasCore()
    try:
        answer = lucas.ask(req.message)
        # getattr, pas un accès direct : plusieurs doublures de test
        # (test_server.py, test_server_intent_mutants.py) n'ont pas cet
        # attribut, ajouté après elles (Brique 1, 08/08/2026).
        destination = getattr(lucas, "last_destination", "local")
    finally:
        lucas.close()

    return {"response": answer, "status": "ok", "destination": destination}


@app.get("/history", dependencies=[Depends(verify_token)])
def history():
    """Retourne l'historique complet de conversation (mémoire SQLite réelle)."""
    lucas = LucasCore()
    try:
        rows = lucas.history()
    finally:
        lucas.close()

    return {
        "history": [
            {"role": role, "content": content}
            for role, content in rows
        ]
    }


@app.get("/system", dependencies=[Depends(verify_token)])
def system_snapshot():
    """
    World Model v1 — snapshot de l'état système en RAM, pas de persistance.
    Voir VISION_LONG_TERME.md §2 : structure Python rafraîchie à la
    demande, pas de graphe de connaissances (GraphRAG) pour l'instant.
    """
    try:
        return get_snapshot()
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Dépendance manquante pour le World Model : {exc}",
        ) from exc


# ── Semantic Desktop (IDEAS.md #16, ROADMAP.md §5.8) — lecture seule ───
#
# Contrepartie mobile du module construit le 03/08/2026 : jusqu'ici
# accessible uniquement en important modules.semantic_desktop côté
# Python, sans route REST. Même garde de jeton que /history — la liste
# des documents personnels de Cyril (noms de fichiers : bulletins,
# attestations...) est aussi révélatrice que l'historique de conversation.
#
# SemanticDesktop() est recréé à chaque appel, comme LucasCore() et
# RAGManager() ailleurs dans ce fichier et dans core/lucas_core.py — même
# raisonnement : aucun état à partager entre requêtes, et éviter un
# singleton partagé entre threads du pool FastAPI.


@app.get("/documents", dependencies=[Depends(verify_token)])
def documents():
    """Documents personnels actuellement indexés (RAG), triés."""
    return {"documents": SemanticDesktop().list_documents()}


@app.get("/documents/periods", dependencies=[Depends(verify_token)])
def documents_by_period():
    """
    Documents regroupés par année détectée (voir
    modules.semantic_desktop.group_by_period — niveau année seul depuis
    le correctif du 03/08/2026, ROADMAP.md §5.8).
    """
    return {"periods": SemanticDesktop().group_by_period()}


@app.get("/documents/{source_id}/related", dependencies=[Depends(verify_token)])
def related_documents(source_id: str, top_k: int = 3):
    """Documents sémantiquement proches de `source_id` (lui-même exclu)."""
    return {"related": SemanticDesktop().related_documents(source_id, top_k=top_k)}


# ── Finance CSV (Phase 2, fermé le 03/08/2026) — lecture seule ─────────
#
# Même situation que Semantic Desktop avant sa route REST : le module
# (modules/finance_manager.py) était construit et testé depuis longtemps,
# mais jamais consultable — ni par le chat (voir should_use_finance()
# dans core/router.py, câblé le même jour), ni par une route REST.
#
# Même garde de jeton que /history et /documents — un solde ou une
# dépense nommée est une donnée ultra-sensible (CLAUDE.md règle 3).
# load_directory() relit data/finance/ à chaque appel plutôt que de
# garder un état en mémoire, même raisonnement que RAGManager()/
# SemanticDesktop() ailleurs dans ce fichier.


@app.get("/finance/summary", dependencies=[Depends(verify_token)])
def finance_summary():
    """
    Résumé des relevés bancaires importés (data/finance/, ignoré par
    git). `has_data=False` si le dossier est vide ou absent — jamais un
    résumé silencieusement vide sans le dire explicitement.
    """
    from modules.finance_manager import load_directory

    manager, skipped_files = load_directory()
    if not manager.transactions:
        return {"has_data": False, "skipped_files": skipped_files}

    dates = [t["date"] for t in manager.transactions]
    return {
        "has_data": True,
        "transaction_count": len(manager.transactions),
        "period": {
            "start": min(dates).strftime("%Y-%m-%d"),
            "end": max(dates).strftime("%Y-%m-%d"),
        },
        "balance": round(manager.get_balance(), 2),
        "income": round(manager.get_income_total(), 2),
        "expenses": round(manager.get_expense_total(), 2),
        "expenses_by_category": {
            category: round(amount, 2)
            for category, amount in manager.get_expenses_by_category().items()
        },
        "uncategorized": [
            {"date": t["date"].strftime("%Y-%m-%d"), "libelle": t["libelle"]}
            for t in manager.get_uncategorized()
        ],
        "skipped_files": skipped_files,
    }


# ── Workspace Luca's (IDEAS.md #102, E-1) ──────────────────────────────
#
# Rend visible ce que Luca's fait déjà : rapports, demandes en attente,
# actions gouvernées, objectifs en cours. Voir modules/workspace_manager.py
# pour le détail de chaque source. Même garde de jeton que /history,
# /documents, /finance/summary — noms de rapports et objectifs
# (potentiellement financiers) sont sensibles.
#
# ⚠️ Plus strictement lecture seule depuis la zone sandbox (E-3, plus
# bas) : /workspace/sandbox/* écrit une proposition de code et son
# résultat. /workspace/summary et /workspace/layout ci-dessous restent
# inchangés, lecture seule pour l'un, écriture de disposition (pas de
# contenu) pour l'autre.


@app.get("/workspace/summary", dependencies=[Depends(verify_token)])
def workspace_summary_route():
    """Instantané complet du Workspace Luca's (E-1) — lecture seule."""
    return workspace_summary()


# ── Disposition du Workspace (glisser-déposer + tailles, 09/08/2026) ───
#
# Seule écriture de cette section : la disposition des 4 cartes (ordre +
# taille), choisie par Cyril, persistée côté serveur pour survivre entre
# appareils/sessions (voir modules/workspace_manager.py, en-tête). Même
# garde de jeton que le reste du Workspace.


@app.get("/workspace/layout", dependencies=[Depends(verify_token)])
def workspace_layout_route():
    """Disposition actuelle (ordre + taille des cartes), ou le défaut si rien n'a encore été choisi."""
    return workspace_get_layout()


@app.put("/workspace/layout", dependencies=[Depends(verify_token)])
def workspace_save_layout_route(req: WorkspaceLayoutRequest):
    """
    Enregistre la disposition choisie par Cyril. 400 sur une disposition
    invalide (carte inconnue/manquante, taille hors S/M/L/XL) — jamais un
    enregistrement partiel ou silencieusement ignoré.
    """
    try:
        workspace_save_layout(req.order, req.sizes)
    except InvalidLayout as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok"}


# ── Zone sandbox du Workspace (E-3, 09/08/2026) ─────────────────────────
#
# Le code proposé reste PROPOSÉ jusqu'à décision explicite (VISION_LONG_TERME.md
# §4, brief cowork_workspace/BRIEF_WORKSPACE_E3_SANDBOX.md §5) : /submit
# n'exécute jamais rien, seul /execute le fait, après que Cyril l'a
# explicitement demandé depuis l'interface — jamais automatique. Même
# garde de jeton que le reste du Workspace.


@app.post("/workspace/sandbox/submit", dependencies=[Depends(verify_token)])
def workspace_sandbox_submit_route(req: SandboxSubmitRequest):
    """Enregistre une proposition de code, statut 'pending'. Ne l'exécute jamais."""
    try:
        return sandbox_submit(req.code)
    except SandboxError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/workspace/sandbox/{run_id}/execute", dependencies=[Depends(verify_token)])
def workspace_sandbox_execute_route(run_id: int):
    """Exécute une proposition 'pending' dans l'environnement isolé (modules/sandbox_runner.py)."""
    try:
        return sandbox_execute(run_id)
    except SandboxError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/workspace/sandbox/{run_id}/reject", dependencies=[Depends(verify_token)])
def workspace_sandbox_reject_route(run_id: int):
    """Marque une proposition 'pending' comme rejetée — ne l'exécute jamais."""
    try:
        return sandbox_reject(run_id)
    except SandboxError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ── Bureau de l'IA (E-5, 09/08/2026) — lecture seule stricte ───────────
#
# Brief nommé "Poste de Commandement IA" (cowork_workspace/BRIEF_POSTE_COMMANDEMENT_IA_E5.md),
# renommé "Bureau de l'IA" par Cyril après coup — même fonctionnalité.
# Page séparée
# (pas une carte du Workspace — la compaction du 09/08/2026, §5.81, laisse
# trop peu de marge pour une 7e carte sans la refaire, choix confirmé par
# Cyril). Même garde de jeton que le reste du Workspace : décrit
# l'architecture réelle de Luca's, pas une donnée personnelle de Cyril,
# mais reste réservé à qui a déjà le jeton, par cohérence.


@app.get("/capabilities", dependencies=[Depends(verify_token)])
def capabilities_route():
    """Instantané des capacités réelles de Luca's — modules/capability_registry.py."""
    return {
        "verified_at": CAPABILITY_REGISTRY_VERIFIED_AT,
        "capabilities": [
            {
                "name": c.name,
                "category": c.category,
                "description": c.description,
                "status": c.status,
                "detail": c.detail,
            }
            for c in list_capabilities()
        ],
    }


# ── WebSocket : canal unique Luca's ↔ Godot ─────────────────────
#
# Le vocabulaire est défini dans api/protocol.py. Il remplace celui
# de Lucas3D/python_service/orion3d_bridge.py, qui était un simple écho
# jamais branché sur Ollama — et qui ne démarre plus depuis websockets 12,
# son handler ayant une signature obsolète.
#
# Passer par cette API plutôt que par un service séparé n'est pas qu'une
# question de doublon : c'est ce qui fait bénéficier l'avatar 3D du
# routage local/cloud, des gardes de sensibilité et de la mémoire. Un
# bridge parallèle les court-circuiterait tous.

SYSTEM_PUSH_INTERVAL = 1.0  # secondes entre deux envois de charge machine


async def _push_system_state(websocket: WebSocket) -> None:
    """
    Envoie la charge machine en continu, pour le HUD Godot.

    Tourne en tâche de fond : sans ça, les jauges ne bougeraient qu'au
    rythme des messages de Cyril, donc resteraient figées la plupart du
    temps.
    """
    while True:
        try:
            snapshot = get_snapshot()
            await websocket.send_json(
                protocol.system(
                    snapshot["cpu_percent"],
                    snapshot["ram_percent"],
                    snapshot.get("gpu_percent", 0.0),
                )
            )
        except Exception:  # noqa: BLE001 — déconnexion ou snapshot
            # indisponible : la boucle s'arrête, le chat continue.
            return
        await asyncio.sleep(SYSTEM_PUSH_INTERVAL)


# 25 minutes (STALE_AFTER dans security/status.py), pas 1 seconde comme la
# charge machine : l'état de sécurité ne bouge qu'au rythme des balayages
# de lucas_daemon.py (5-15 min), lire les deux bases SQLite plus souvent
# n'apprendrait rien de plus, juste du travail disque en pure perte.
SECURITY_PUSH_INTERVAL = 30.0


async def _push_security_status(websocket: WebSocket) -> None:
    """
    État des capteurs niveau 1, pour le panneau des privilèges (IDEAS.md
    #78, décision Cyril du 02/08/2026). Lit ce que lucas_daemon.py a déjà
    produit — ne déclenche jamais de balayage lui-même (voir
    security/status.py, en-tête).
    """
    while True:
        try:
            status = get_security_status()
            await websocket.send_json(
                protocol.security_status(
                    status.active,
                    status.last_scan_at,
                    status.findings_24h,
                    status.latest_summary,
                )
            )
        except Exception:  # noqa: BLE001 — déconnexion ou bases absentes :
            # la boucle s'arrête, le chat continue (même garde que
            # _push_system_state ci-dessus).
            return
        await asyncio.sleep(SECURITY_PUSH_INTERVAL)


def _save_base64_image(image_base64: str) -> str:
    """
    Décode une photo base64 (message WebSocket "image", pont mobile) vers
    un fichier temporaire. Même logique que STTEngine.transcribe_base64()
    pour l'audio — décodage et écriture disque, la suppression reste à la
    charge de l'appelant, une fois LucasCore.ask() terminé.

    Lève sur base64 invalide plutôt que de rendre un chemin bidon : mieux
    vaut un message d'erreur clair côté client qu'un fichier vide envoyé
    à l'OCR.
    """
    raw = base64.b64decode(image_base64, validate=True)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(raw)
        return tmp.name


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Vérifié AVANT accept() : un jeton absent/invalide ferme la connexion
    # au niveau protocole (code 1008, violation de politique), sans jamais
    # l'ouvrir.
    #
    # Le jeton arrive par l'en-tête `Sec-WebSocket-Protocol`, pas par la
    # query string. Un WebSocket de navigateur ne peut pas poser d'en-tête
    # personnalisé — c'est la raison pour laquelle la query string avait été
    # retenue au départ — mais il peut annoncer des sous-protocoles, qui
    # voyagent DANS un en-tête standard. Un en-tête n'est pas journalisé au
    # niveau INFO, contrairement à la ligne de requête : le jeton cesse donc
    # d'atterrir en clair dans data/logs/server_startup.log.
    #
    # La query string reste acceptée en repli, pour les clients qui ne
    # peuvent pas connaître cette convention (tests, curl, futur client
    # Godot). Ce chemin-là est couvert par le masquage de api/log_scrub.py.
    fourni = _token_from_subprotocols(websocket)
    if fourni is None:
        fourni = websocket.query_params.get("token")

    if not _token_is_valid(fourni):
        await websocket.close(code=1008)
        return

    # Un navigateur ferme la connexion si le serveur sélectionne un
    # sous-protocole qu'il n'a pas proposé — d'où le test d'appartenance
    # plutôt qu'un renvoi inconditionnel. Seul WS_SUBPROTOCOL est renvoyé,
    # jamais celui qui porte le jeton : il sert de véhicule, pas de
    # protocole négocié.
    proposes = websocket.scope.get("subprotocols") or []
    await websocket.accept(
        subprotocol=WS_SUBPROTOCOL if WS_SUBPROTOCOL in proposes else None
    )
    await websocket.send_json(protocol.avatar_state(protocol.STATE_IDLE))

    pusher = asyncio.create_task(_push_system_state(websocket))
    security_pusher = asyncio.create_task(_push_security_status(websocket))

    # Identifié via le "hello" — décide si la vision écran AUTOMATIQUE
    # (should_use_vision, plus bas) a un sens pour ce client. Godot tourne
    # toujours sur ce PC, donc "mon écran" y désigne sans ambiguïté ce que
    # Cyril a sous les yeux. La PWA peut tourner n'importe où (le
    # téléphone, ailleurs que devant ce PC) — capturer l'écran du PC en
    # silence pendant que Cyril n'est peut-être pas devant serait une vraie
    # faute de confidentialité, pas un détail technique. Défaut sûr :
    # "pc" tant qu'aucun "hello" n'a rien dit (préserve le comportement
    # historique, et celui des tests qui n'envoient jamais de "hello").
    client_type = "pc"

    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type", "")
            # Chemin d'une photo décodée (message "image" ci-dessous) — None
            # pour "chat"/"audio", qui n'en fournissent pas.
            image_path = None

            # Poignée de main du client Godot (scripts/websocket_client.gd)
            # ou de la PWA (static/js/websocket.js).
            if message_type == "hello":
                if data.get("client") == "lucas_pwa":
                    client_type = "mobile"
                await websocket.send_json(
                    protocol.chat("Luca's est connectée.", from_luca=True)
                )
                continue

            if message_type == "chat":
                message = protocol.read_user_text(data)

            elif message_type == "image":
                # Pont mobile (Phase 4) : le téléphone photographie ce que
                # le PC ne peut pas voir lui-même (pas de caméra — voir
                # VISION_LONG_TERME.md §2 Pilier 3). MÊME pipeline vision que
                # l'écran (core.LucasCore._describe_image_at), jamais un
                # second chemin OCR/VLM parallèle.
                image_base64 = protocol.read_user_image(data)
                if not image_base64:
                    continue

                try:
                    image_path = _save_base64_image(image_base64)
                except Exception as exc:  # noqa: BLE001 — base64 invalide
                    await websocket.send_json(
                        protocol.error(f"Image illisible : {exc}")
                    )
                    await websocket.send_json(protocol.avatar_state(protocol.STATE_IDLE))
                    continue

                message = protocol.read_user_text(data) or "Décris ce que tu vois."

            elif message_type == "audio":
                # Pont mobile (Phase 4) : le S25 Ultra envoie l'audio, le PC
                # n'a pas de micro (VISION_LONG_TERME.md §2, Pilier 3). Ce
                # bloc est le premier appelant réel de modules/stt_engine.py
                # — jusqu'ici écrit et testé, mais rien ne l'alimentait.
                audio_base64 = protocol.read_user_audio(data)
                if not audio_base64:
                    continue

                # LISTENING existait dans le protocole depuis les 5 modes de
                # présence, mais restait inactif faute de micro — c'est le
                # premier moment où il a un sens réel à émettre.
                await websocket.send_json(
                    protocol.avatar_state(protocol.STATE_LISTENING)
                )
                try:
                    transcript = _stt_engine.transcribe_base64(audio_base64)
                    message = transcript.text
                    # Diagnostic (bug micro remonté le 05/08/2026, cause non
                    # confirmée — voir static/js/audio.js) : la durée que
                    # Whisper a réellement détectée, à comparer à celle
                    # mesurée côté client (console du navigateur) pour savoir
                    # si l'enregistrement envoyé est déjà incomplet ou si le
                    # problème est ailleurs.
                    await websocket.send_json(
                        protocol.activity(
                            "voice",
                            f"micro — {transcript.duration_seconds:.1f}s détectées, "
                            f"{len(message)} caractère(s) transcrit(s)",
                        )
                    )
                except STTUnavailable as exc:
                    # Même logique que le chemin vision plus bas : un doute
                    # sur l'audio ne doit jamais planter la connexion, mais
                    # ici Cyril doit savoir qu'on ne l'a pas entendu — un
                    # silence serait plus trompeur qu'un message d'erreur.
                    await websocket.send_json(
                        protocol.error(f"Audio illisible : {exc}")
                    )
                    await websocket.send_json(protocol.avatar_state(protocol.STATE_IDLE))
                    continue
                except Exception as exc:  # noqa: BLE001 — voir ci-dessous
                    # ⚠️ Élargi le 05/08/2026. Seul `STTUnavailable` était
                    # rattrapé : toute autre panne (fichier audio corrompu,
                    # décodeur absent, mémoire) remontait hors du handler et
                    # FERMAIT la connexion WebSocket. Côté PWA, Cyril voyait
                    # le bandeau clignoter puis se reconnecter, sans jamais
                    # savoir que sa phrase avait été perdue — une panne
                    # déguisée en hoquet réseau.
                    await websocket.send_json(
                        protocol.error(f"Transcription impossible : {type(exc).__name__}")
                    )
                    await websocket.send_json(protocol.avatar_state(protocol.STATE_IDLE))
                    continue

                if not message.strip() or not transcript.is_confident:
                    # ⚠️ LE SILENCE QUI CORRESPOND AU BUG MICRO DE CYRIL
                    # (05/08/2026). Avant : retour à IDLE, sans un mot. Il
                    # appuyait sur le micro, parlait, et il ne se passait
                    # RIEN — indiscernable d'un bouton cassé, d'un serveur
                    # muet ou d'une phrase ignorée.
                    #
                    # ⚠️ `is_confident` est ARRIVÉ APRÈS, et c'est le test
                    # réel qui l'a imposé. Le correctif ne testait d'abord
                    # que la chaîne vide — les tests unitaires passaient.
                    # Confronté au vrai moteur Whisper sur un WAV de
                    # silence pur, le résultat n'est PAS une chaîne vide :
                    #
                    #   silence 2 s -> texte 'You',  confiance 0,349
                    #   silence 3 s -> texte 'You',  confiance 0,305
                    #   parole réelle -> texte juste, confiance 0,995
                    #
                    # Whisper HALLUCINE un mot court et plausible sur du
                    # silence. Ce mot serait parti au LLM, qui aurait
                    # répondu à du vide — observé exactement ainsi en test
                    # réel avant ce correctif.
                    #
                    # La confiance sépare les deux cas sans ambiguïté (0,3
                    # contre 0,99), et `TranscriptResult.is_confident`
                    # existait déjà, testé, depuis la construction du
                    # module — simplement jamais consulté par ce serveur.
                    #
                    # Même doctrine que les blocs de contexte du prompt :
                    # une capacité qui ne produit rien doit le DIRE.
                    await websocket.send_json(
                        protocol.activity(
                            "voice",
                            f"micro — {transcript.duration_seconds:.1f}s reçues, "
                            f"confiance {transcript.confidence:.2f} : aucune parole "
                            "reconnue",
                        )
                    )
                    await websocket.send_json(
                        protocol.error(
                            "Je n'ai rien compris — parle un peu plus fort ou "
                            "rapproche-toi du micro."
                        )
                    )
                    await websocket.send_json(protocol.avatar_state(protocol.STATE_IDLE))
                    continue

            else:
                continue

            if not message:
                continue

            # ⚠️ WATCHING est le TÉMOIN DE CAPTURE D'ÉCRAN — l'équivalent
            # de la LED d'une webcam. Il existait dans le protocole et
            # dans les poses du visage Godot, mais RIEN NE L'ÉMETTAIT :
            # le serveur ne connaissait que idle / thinking / speaking.
            # Le client 3D ne pouvait donc jamais montrer que Luca's est
            # en train de regarder l'écran, alors que l'UI PySide6 le fait
            # depuis le début. Cyril a acté ce témoin comme un signal de
            # confidentialité, pas comme une décoration.
            #
            # La décision est prise AVANT l'appel : lucas.ask() capture
            # l'écran à l'intérieur, et prévenir après coup n'aurait aucun
            # intérêt — c'est pendant la capture que le témoin compte.
            # ⚠️ Bug trouvé par Cyril en test réel (02/08/2026, premier essai
            # mobile) : "que peux-tu voir sur mes écrans ?" envoyé en texte
            # depuis la PWA a capturé l'écran du PC — should_use_vision() ne
            # sait pas QUI a posé la question, seulement CE QU'elle dit. Le
            # même texte, tapé sur la PWA (peut-être loin du PC) ou dans
            # Godot (toujours devant le PC), ne doit pas produire la même
            # action. allow_screen_capture porte cette distinction : jamais
            # de capture PC silencieuse pour un client mobile.
            allow_screen_capture = client_type != "mobile"

            lucas = LucasCore()
            if image_path is not None:
                # Photo du téléphone : le bouton caméra EST le signal, pas
                # besoin du classifieur — même témoin WATCHING que pour
                # l'écran, réutilisé à l'identique (voir
                # VISION_LONG_TERME.md §2 Pilier 3, précision du 02/08/2026).
                regarde = True
            else:
                try:
                    # mentions_pc_explicitly() lève la restriction mobile
                    # quand Cyril nomme le PC sans ambiguïté (voir
                    # core/lucas_core.py) — WATCHING doit rester le témoin
                    # fidèle de la VRAIE capture, pas seulement du client.
                    regarde = should_use_vision(message, lucas.recent_context()) and (
                        allow_screen_capture or mentions_pc_explicitly(message)
                    )
                except Exception:  # noqa: BLE001 — un doute sur l'état ne doit
                    # jamais empêcher de répondre.
                    regarde = False

            await websocket.send_json(
                protocol.avatar_state(
                    protocol.STATE_WATCHING if regarde else protocol.STATE_THINKING
                )
            )

            # Console de flux (IDEAS.md #77). LucasCore.ask() est un appel
            # SYNCHRONE unique — impossible d'envoyer chaque événement au
            # fil de l'eau sans rendre tout le pipeline asynchrone, ce qui
            # dépasserait largement la construction de la console. Les
            # événements sont donc COLLECTÉS pendant ask(), puis envoyés
            # d'un coup juste avant la réponse : pas du vrai temps réel,
            # mais les horodatages restent fidèles à quand chaque étape a
            # réellement eu lieu — voir protocol.activity().
            activity_events: list[tuple[str, str]] = []

            try:
                answer = lucas.ask(
                    message,
                    image_path=image_path,
                    allow_screen_capture=allow_screen_capture,
                    # B023 assumé ci-dessous : la liaison tardive est inoffensive.
                    # `activity_events` est recréée à chaque tour (l.693),
                    # `ask()` est synchrone, et la liste est relue juste
                    # après (l.707) — la lambda ne survit jamais à son
                    # itération. Restructurer n'apporterait rien.
                    on_activity=lambda kind, text: activity_events.append((kind, text)),  # noqa: B023
                )
            finally:
                lucas.close()
                if image_path is not None:
                    Path(image_path).unlink(missing_ok=True)

            for kind, text in activity_events:
                await websocket.send_json(protocol.activity(kind, text))

            # Deux messages plutôt qu'un : l'état pilote l'animation du
            # visage, le message de chat alimente la bulle du HUD. Le
            # client Godot lit déjà « chat » nativement.
            await websocket.send_json(
                protocol.avatar_state(protocol.STATE_SPEAKING, answer)
            )
            await websocket.send_json(
                protocol.chat(
                    answer, from_luca=True,
                    destination=getattr(lucas, "last_destination", "local"),
                )
            )

            # Voix (pont mobile TTS) : le texte part D'ABORD, la synthèse
            # ensuite — edge_tts prend plusieurs secondes (réseau), et
            # Cyril ne doit pas attendre l'audio pour lire la réponse.
            # Optionnelle, jamais déclenchée sans le demander explicitement
            # (voir protocol.read_speak_flag) — même défaut que le toggle
            # TTS Auto de l'UI PySide6.
            if protocol.read_speak_flag(data):
                try:
                    audio_path = await asyncio.to_thread(
                        _voice_manager.synthesize_routed, answer, message
                    )
                except Exception as exc:  # noqa: BLE001 — une panne TTS ne
                    # doit jamais invalider une réponse texte déjà envoyée.
                    await websocket.send_json(
                        protocol.activity("voice", f"voix indisponible : {exc}"[:120])
                    )
                else:
                    if audio_path:
                        # Lecture DANS UN THREAD, comme la synthèse ci-dessus :
                        # un `open()` bloquant ici gèlerait la boucle
                        # d'événements — donc TOUTES les connexions
                        # WebSocket — le temps de lire le fichier audio.
                        # Le déport était déjà fait pour la synthèse
                        # (asyncio.to_thread l.726) ; la lecture avait été
                        # oubliée. Trouvé par ruff ASYNC230 le 06/08/2026.
                        audio_b64 = await asyncio.to_thread(_read_audio_b64, audio_path)
                        mime = _audio_mime_type(audio_path)
                        # Chaque synthèse produit désormais un fichier UNIQUE
                        # (modules/voice_manager.py, corrigé le 05/08/2026 —
                        # un chemin fixe partagé causait une course entre
                        # connexions concurrentes, voir ROADMAP.md). Un
                        # fichier lu une fois n'a plus de raison de rester.
                        Path(audio_path).unlink(missing_ok=True)
                        await websocket.send_json(protocol.speech(audio_b64, mime))
                        await websocket.send_json(
                            protocol.activity(
                                "voice", f"voix synthétisée ({mime.split('/')[-1]})"
                            )
                        )
                    else:
                        # synthesize_routed() rend None sur contenu sensible
                        # + voix locale indisponible
                        # (modules/voice_manager.py) — jamais un silence
                        # côté PWA : Cyril doit savoir que la voix a été
                        # sciemment coupée, pas qu'elle a échoué.
                        await websocket.send_json(
                            protocol.activity(
                                "voice",
                                "voix non prononcée — contenu sensible, "
                                "voix locale indisponible",
                            )
                        )

            await websocket.send_json(protocol.avatar_state(protocol.STATE_IDLE))

    except WebSocketDisconnect:
        pass
    finally:
        pusher.cancel()
        security_pusher.cancel()


# ── PWA mobile (pont mobile, Phase 4) ──────────────────────────────────
#
# Montée à /app plutôt qu'à la racine, pour ne jamais entrer en collision
# avec les routes JSON ci-dessus (/status, /chat, /history, /system) ni
# avec /ws. html=True sert index.html sur /app/ et sur tout chemin non
# trouvé sous /app — nécessaire pour une PWA à page unique.
#
# Montée en DERNIER : FastAPI résout les routes dans l'ordre de
# déclaration, et un mount capte tout ce qui commence par son préfixe —
# la déclarer avant les routes ci-dessus les aurait rendues inatteignables.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/app", StaticFiles(directory=STATIC_DIR, html=True), name="pwa")


if __name__ == "__main__":
    import uvicorn

    from config import API_HOST, API_PORT

    # 127.0.0.1 par défaut : l'API n'a aucune authentification et
    # /history expose toutes les conversations. Voir config.py.
    uvicorn.run(app, host=API_HOST, port=API_PORT)