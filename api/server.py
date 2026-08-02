# api/server.py — API FastAPI unique de Luca's
#
# Pourquoi une seule API (et pas un serveur séparé pour Godot) ?
# Un seul point de vérité, moins de code à maintenir en double.
# Le mobile (PWA) utilise les routes REST classiques ci-dessous.
# Godot utilisera plus tard l'endpoint WebSocket /ws (protocole minimal,
# voir VISION_LONG_TERME.md §2, Pilier 3 — le corps étendu PC + mobile).

import asyncio
import sys
from pathlib import Path

# Permet de lancer ce fichier directement (uvicorn api.server:app depuis la racine)
# ou en important le module depuis un autre script, sans casser les imports relatifs.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api import protocol
from core.lucas_core import LucasCore
from core.router import should_use_vision
from core.world_model import get_snapshot

app = FastAPI(title="Luca's API", version="0.2")

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


# ── Endpoints REST ──────────────────────────────────────────────

@app.get("/status")
def status():
    """Ping simple — confirme que le serveur tourne."""
    return {"status": "running", "version": "0.2"}


@app.post("/chat")
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


@app.get("/history")
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


@app.get("/system")
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


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json(protocol.avatar_state(protocol.STATE_IDLE))

    pusher = asyncio.create_task(_push_system_state(websocket))

    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type", "")

            # Poignée de main du client Godot (scripts/websocket_client.gd).
            if message_type == "hello":
                await websocket.send_json(
                    protocol.chat("Luca's est connectée.", from_luca=True)
                )
                continue

            if message_type != "chat":
                continue

            message = protocol.read_user_text(data)
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
            lucas = LucasCore()
            try:
                regarde = should_use_vision(message, lucas.recent_context())
            except Exception:  # noqa: BLE001 — un doute sur l'état ne doit
                # jamais empêcher de répondre.
                regarde = False

            await websocket.send_json(
                protocol.avatar_state(
                    protocol.STATE_WATCHING if regarde else protocol.STATE_THINKING
                )
            )

            try:
                answer = lucas.ask(message)
            finally:
                lucas.close()

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


if __name__ == "__main__":
    import uvicorn

    from config import API_HOST, API_PORT

    # 127.0.0.1 par défaut : l'API n'a aucune authentification et
    # /history expose toutes les conversations. Voir config.py.
    uvicorn.run(app, host=API_HOST, port=API_PORT)