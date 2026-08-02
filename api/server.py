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

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api import protocol
from config import API_TOKEN
from core.lucas_core import LucasCore
from core.router import mentions_pc_explicitly, should_use_vision
from core.world_model import get_snapshot
from modules.stt_engine import STTEngine, STTUnavailable

app = FastAPI(title="Luca's API", version="0.2")

# Instance unique, partagée entre tous les messages « audio » du WebSocket.
# Contrairement à LucasCore (recréé par appel à cause de SQLite, voir plus
# bas), STTEngine ne touche à aucune base — le websocket est géré dans la
# boucle asyncio, un seul thread, donc pas de risque à la partager. La
# recréer par message rechargerait le modèle Whisper à chaque phrase.
_stt_engine = STTEngine()

# CORS ouvert pour l'instant (dev local uniquement).
# À restreindre à l'IP du mobile une fois le PWA en place (S5).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # La spec CORS interdit credentials + origine « * » : les navigateurs
    # rejettent la combinaison. False reflète ce qui se passe réellement.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


# ── Jeton partagé (prérequis pour le pont mobile, ROADMAP.md §2) ───────
#
# Posé le 02/08/2026, SANS EFFET aujourd'hui : API_TOKEN est vide par
# défaut (config.py), et un jeton vide désactive la vérification —
# exactement le comportement d'avant. Il ne devient contraignant que le
# jour où Cyril renseigne une valeur dans .env, ce qui doit précéder tout
# passage de API_HOST à "0.0.0.0", jamais le suivre.


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
    finally:
        lucas.close()

    return {"response": answer, "status": "ok"}


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
    # l'ouvrir. Par requête (pas par en-tête, comme le REST ci-dessus) —
    # un websocket de navigateur ne peut pas poser d'en-tête personnalisé,
    # alors qu'une query string reste lisible par les trois clients visés
    # (PWA, Godot, tests).
    if not _token_is_valid(websocket.query_params.get("token")):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    await websocket.send_json(protocol.avatar_state(protocol.STATE_IDLE))

    pusher = asyncio.create_task(_push_system_state(websocket))

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

                if not message:
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

            try:
                answer = lucas.ask(
                    message, image_path=image_path, allow_screen_capture=allow_screen_capture
                )
            finally:
                lucas.close()
                if image_path is not None:
                    Path(image_path).unlink(missing_ok=True)

            # Deux messages plutôt qu'un : l'état pilote l'animation du
            # visage, le message de chat alimente la bulle du HUD. Le
            # client Godot lit déjà « chat » nativement.
            await websocket.send_json(
                protocol.avatar_state(protocol.STATE_SPEAKING, answer)
            )
            await websocket.send_json(protocol.chat(answer, from_luca=True))
            await websocket.send_json(protocol.avatar_state(protocol.STATE_IDLE))

    except WebSocketDisconnect:
        pass
    finally:
        pusher.cancel()


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