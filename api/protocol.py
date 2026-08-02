# api/protocol.py — vocabulaire du canal WebSocket Luca's ↔ Godot
#
# ── Pourquoi ce module existe ─────────────────────────────────────────
#
# Il existait deux protocoles incompatibles :
#
#   • api/server.py  — « avatar_state » / « chat », port 8000, branché
#     sur LucasCore, donc sur le vrai routage et les vraies gardes
#   • Lucas3D/python_service/orion3d_bridge.py — « speak » / « idle » /
#     « system », port 8765, simple écho jamais connecté à Ollama
#
# Le client Godot pointait sur le second. Résultat : l'avatar 3D ne
# pouvait dialoguer qu'avec un service qui répétait les messages, et qui
# ne démarre même plus (handler incompatible avec websockets ≥ 12).
#
# Ce module fixe UN vocabulaire, côté Python, que Godot consommera. Les
# noms d'état sont ceux de l'avatar PySide6 (ui/avatar_widget.py) : une
# seule liste d'états pour les deux interfaces, sinon elles divergeront.

from typing import Any

# Les cinq modes de présence, en minuscules pour le transport JSON.
# Doivent rester alignés sur ui/avatar_widget.PRESENCE_STATES.
STATE_IDLE = "idle"
STATE_THINKING = "thinking"
STATE_SPEAKING = "speaking"
STATE_WATCHING = "watching"
STATE_LISTENING = "listening"

PRESENCE_STATES = (
    STATE_IDLE,
    STATE_THINKING,
    STATE_SPEAKING,
    STATE_WATCHING,
    STATE_LISTENING,
)


def avatar_state(state: str, text: str = "") -> dict:
    """
    État de présence de Luca's.

    Un état inconnu retombe sur « idle » plutôt que d'être transmis tel
    quel : le client afficherait un halo sans couleur, ou rien du tout.
    """
    if state not in PRESENCE_STATES:
        state = STATE_IDLE
    message: dict[str, Any] = {"type": "avatar_state", "state": state}
    if text:
        message["text"] = text
    return message


def chat(text: str, from_luca: bool = True) -> dict:
    """
    Message de conversation.

    Le champ s'appelait « from_orion » avant le renommage technique du
    02/08/2026 (voir ROADMAP §6) — renommé en même temps que le client
    Godot (scripts/websocket_client.gd), sur les deux faces du contrat.
    """
    return {"type": "chat", "text": text, "from_lucas": from_luca}


def system(cpu: float, ram: float, gpu: float = 0.0) -> dict:
    """
    Charge machine pour le HUD.

    Ces trois champs sont exactement ceux qu'attend widget_system.gd.
    Le GPU vaut 0 quand il n'est pas lisible : le HUD affiche alors une
    jauge vide plutôt que de disparaître.
    """
    return {
        "type": "system",
        "cpu": round(float(cpu), 1),
        "ram": round(float(ram), 1),
        "gpu": round(float(gpu), 1),
    }


def error(detail: str) -> dict:
    """Panne côté serveur, à afficher plutôt qu'à laisser en silence."""
    return {"type": "error", "detail": detail}


def read_user_text(data: dict) -> str:
    """
    Extrait le texte d'un message entrant, quel que soit le champ.

    Le client Godot envoie « text », l'ancien protocole de l'API
    envoyait « message ». Accepter les deux évite de casser l'un des
    deux clients pendant la transition — et coûte une ligne.
    """
    if not isinstance(data, dict):
        return ""
    for field in ("message", "text"):
        value = data.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def read_user_audio(data: dict) -> str:
    """
    Extrait l'audio base64 d'un message entrant de type « audio ».

    Format attendu du S25 Ultra (pont mobile, Phase 4) : un seul champ
    « audio_base64 ». Pas de deuxième nom accepté ici — contrairement au
    texte, ce protocole n'a pas d'ancien client à ménager.
    """
    if not isinstance(data, dict):
        return ""
    value = data.get("audio_base64")
    return value.strip() if isinstance(value, str) and value.strip() else ""
