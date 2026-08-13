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

# source_agent : hook multi-agents (IDEAS.md #38, toujours reporté v1.1+ —
# CLAUDE.md règle 12) posé le 03/08/2026 à la demande de Cyril. Un seul
# agent existe aujourd'hui — cette valeur ne varie jamais, rien ne la lit
# côté client. Coûte une ligne par message, évite de devoir retoucher tout
# le protocole si un jour plusieurs agents émettent sur ce canal.
DEFAULT_SOURCE_AGENT = "main"

# Les sept modes de présence, en minuscules pour le transport JSON.
# Doivent rester alignés sur ui/avatar_widget.PRESENCE_STATES — passé de
# 5 à 7 le 08/08/2026 (Brique 4 du noyau minimal) : THINKING_DEEP
# (escalade cloud, Brique 1) et OBSERVING (présence soutenue, distincte
# de WATCHING qui reste une capture ponctuelle).
STATE_IDLE = "idle"
STATE_THINKING = "thinking"
STATE_THINKING_DEEP = "thinking_deep"
STATE_SPEAKING = "speaking"
STATE_WATCHING = "watching"
STATE_OBSERVING = "observing"
STATE_LISTENING = "listening"

PRESENCE_STATES = (
    STATE_IDLE,
    STATE_LISTENING,
    STATE_WATCHING,
    STATE_OBSERVING,
    STATE_SPEAKING,
    STATE_THINKING,
    STATE_THINKING_DEEP,
)


def avatar_state(state: str, text: str = "") -> dict:
    """
    État de présence de Luca's.

    Un état inconnu retombe sur « idle » plutôt que d'être transmis tel
    quel : le client afficherait un halo sans couleur, ou rien du tout.
    """
    if state not in PRESENCE_STATES:
        state = STATE_IDLE
    message: dict[str, Any] = {
        "type": "avatar_state",
        "state": state,
        "source_agent": DEFAULT_SOURCE_AGENT,
    }
    if text:
        message["text"] = text
    return message


def chat(text: str, from_luca: bool = True, destination: str | None = None) -> dict:
    """
    Message de conversation.

    Le champ s'appelait « from_orion » avant le renommage technique du
    02/08/2026 (voir ROADMAP §6) — renommé en même temps que le client
    Godot (scripts/websocket_client.gd), sur les deux faces du contrat.

    `destination` (ajouté 08/08/2026, Brique 1 — routeur hybride) : "local"
    ou "cloud", provenance de la réponse. Additif, absent si non fourni —
    ignoré sans casse côté Godot, qui ne le lit pas.
    """
    message: dict = {
        "type": "chat",
        "text": text,
        "from_lucas": from_luca,
        "source_agent": DEFAULT_SOURCE_AGENT,
    }
    if destination is not None:
        message["destination"] = destination
    return message


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
        "source_agent": DEFAULT_SOURCE_AGENT,
    }


def security_status(
    active: bool,
    last_scan_at: str | None,
    findings_24h: int,
    latest_summary: str | None,
) -> dict:
    """
    État des capteurs de sécurité niveau 1 — panneau des privilèges
    (IDEAS.md #78). Voir security/status.py pour la provenance des
    champs et pourquoi aucune gravité n'y figure.

    `active` à False doit être affiché clairement, pas masqué : un
    daemon éteint qui laisse croire à une protection en place serait
    pire que l'absence d'indicateur — même principe que le RAG sans
    résultat (core/lucas_core.py).
    """
    message: dict = {
        "type": "security_status",
        "active": active,
        "findings_24h": findings_24h,
        "source_agent": DEFAULT_SOURCE_AGENT,
    }
    if last_scan_at:
        message["last_scan_at"] = last_scan_at
    if latest_summary:
        message["latest_summary"] = latest_summary
    return message


def speech(audio_base64: str, mime: str) -> dict:
    """
    Réponse vocale synthétisée — pont mobile TTS. Le routage local/cloud
    est déjà tranché avant l'appel (core.router.route_voice(),
    modules/voice_manager.py) : ce message ne transporte que le
    résultat, jamais la décision.

    ⚠️ Nommé « speech », pas « audio » : le type ENTRANT « audio »
    désigne déjà le micro du téléphone (capture, voir read_user_audio()
    ci-dessous). Réutiliser le même mot dans l'autre sens aurait été un
    piège pour quiconque relit le protocole plus tard — même sens que
    ceux du client, pas le nom qu'on utilise pour en parler.
    """
    return {
        "type": "speech",
        "audio_base64": audio_base64,
        "mime": mime,
        "source_agent": DEFAULT_SOURCE_AGENT,
    }


def read_speak_flag(data: dict) -> bool:
    """
    Cyril veut-il une réponse vocale pour ce message ?

    Optionnel, faux par défaut : la voix ne doit jamais se déclencher
    sans que ce soit explicitement demandé — voir
    static/js/voice_output.js, qui reflète le bouton 🔊/🔇 de la PWA,
    lui-même désactivé par défaut (même défaut que le toggle TTS Auto de
    l'UI PySide6, ui/main_window.py).
    """
    if not isinstance(data, dict):
        return False
    return bool(data.get("speak"))


def read_conversation_mode_flag(data: dict) -> bool:
    """
    Ce message "audio" vient-il du mode conversation mains libres
    (static/js/conversation_mode.js), pas d'un push-to-talk ponctuel ?

    Seul ce cas déclenche la détection de commande vocale d'arrêt
    (core/voice_commands.is_stop_command) côté serveur — dire "stop" en
    push-to-talk classique doit rester un message normal envoyé à
    Luca's, jamais une action cachée. Faux par défaut, comme
    read_speak_flag().
    """
    if not isinstance(data, dict):
        return False
    return bool(data.get("conversation_mode"))


def error(detail: str) -> dict:
    """Panne côté serveur, à afficher plutôt qu'à laisser en silence."""
    return {"type": "error", "detail": detail, "source_agent": DEFAULT_SOURCE_AGENT}


def voice_command(action: str) -> dict:
    """
    Commande vocale reconnue dans une transcription du mode conversation
    (core/voice_commands.is_stop_command) — jamais envoyée à LucasCore.ask(),
    c'est le tour ENTIER qui est intercepté avant d'atteindre le modèle.

    Un seul type émis aujourd'hui ("stop"), mais gardé sous forme de
    message générique {type, action} plutôt qu'un type "stop_command" dédié
    — un futur "pause"/"répète" tiendrait dans le même vocabulaire, sans
    toucher au protocole.
    """
    return {"type": "voice_command", "action": action, "source_agent": DEFAULT_SOURCE_AGENT}


# ── Pont capteurs téléphone → session PC (12/08/2026) ──────────────────
#
# Le téléphone sert de micro/appareil photo au Luca's du PC, le temps que
# le vrai matériel arrive (D-6). Ces deux messages ne partent QUE vers les
# clients desktop enregistrés (api/server.py, fan-out) — jamais vers le
# mobile émetteur, qui a déjà sa propre réponse par le chemin normal.
#
# ⚠️ Type distinct de "chat" volontairement, plutôt qu'un champ de plus
# sur un message existant : un client qui ne connaît pas "sensor_message"
# l'ignore silencieusement (websocket.js a un `default: break`, le match
# de Godot n'a pas de branche par défaut). Ajouter un champ à "chat"
# aurait au contraire fait afficher deux fois la même réponse par tout
# client déjà en place.


def sensor_message(role: str, text: str, speak_here: bool = False) -> dict:
    """
    Un tour de conversation capté par le téléphone, relayé vers le PC.

    `role` vaut "user" (la question, déjà transcrite par Whisper côté
    serveur) ou "assistant" (la réponse de Luca's) — mêmes valeurs que la
    colonne `role` de la table `conversations`, pour que le desktop les
    affiche avec le code d'affichage qu'il utilise déjà pour son propre
    historique.

    `speak_here` : le PC doit prononcer cette réponse sur ses enceintes.
    Seul le TEXTE voyage, jamais l'audio — le desktop a déjà son propre
    VoiceManager/pygame (ui/main_window.py, TTSWorker), et refaire passer
    un fichier son sur le WebSocket alors que les deux processus tournent
    sur la même machine serait payer un transport pour rien.
    """
    return {
        "type": "sensor_message",
        "role": role,
        "text": text,
        "speak_here": speak_here,
        "source_agent": DEFAULT_SOURCE_AGENT,
    }


def sensor_status(active: bool) -> dict:
    """
    Le mode « capteur pour le PC » vient d'être allumé ou éteint côté
    téléphone — sert l'indicateur visible du desktop.

    Envoyé sur bascule explicite de Cyril, jamais déduit d'un silence :
    l'extinction doit être aussi certaine que l'allumage, sinon
    l'indicateur resterait allumé après que le téléphone a été rangé.
    """
    return {
        "type": "sensor_status",
        "active": bool(active),
        "source_agent": DEFAULT_SOURCE_AGENT,
    }


def read_pc_sensor_flag(data: dict) -> bool:
    """
    Ce message doit-il être traité comme une entrée de la session PC ?

    Faux par défaut, comme read_speak_flag()/read_conversation_mode_flag() :
    le relais vers le PC ne s'active que si le téléphone le demande
    explicitement, jamais par défaut silencieux (brief §4).
    """
    if not isinstance(data, dict):
        return False
    return bool(data.get("pc_sensor"))


# "phone" plutôt que "mobile" : c'est l'appareil qui parle, pas le type de
# client — le desktop pourrait un jour être une tablette sans que ce
# vocabulaire devienne faux.
TTS_TARGETS = ("phone", "pc")
DEFAULT_TTS_TARGET = "phone"


def read_tts_target(data: dict) -> str:
    """
    De quel côté Luca's doit-elle parler : le téléphone ou le PC ?

    Défaut "phone" — le comportement d'aujourd'hui. Une valeur inconnue
    retombe sur le défaut plutôt que de lever : un client mal à jour doit
    dégrader vers le comportement historique, pas casser le tour.
    """
    if not isinstance(data, dict):
        return DEFAULT_TTS_TARGET
    value = data.get("tts_target")
    if isinstance(value, str) and value in TTS_TARGETS:
        return value
    return DEFAULT_TTS_TARGET


# Émis pendant LucasCore.ask() (voir core/lucas_core.py, paramètre
# on_activity) — pas une liste fermée à valider, juste ce que le serveur
# émet aujourd'hui. Un « kind » inconnu ne casse rien côté client : la
# console de flux affiche une puce générique plutôt que rien.
ACTIVITY_KINDS = ("routed", "screen_read", "documents_searched", "answered", "voice")


def activity(kind: str, text: str) -> dict:
    """
    Un pas du traitement en cours — console de flux (IDEAS.md #77).

    Purement informatif : aucun client n'a besoin de le comprendre pour
    fonctionner. Godot l'ignore silencieusement (son match sur "type" n'a
    pas de branche par défaut, voir test_protocol.py). Le texte arrive
    déjà en français, prêt à afficher tel quel.

    ⚠️ Pas de vrai temps réel : LucasCore.ask() est un appel synchrone
    unique, les événements sont collectés pendant son exécution puis
    envoyés d'un coup à la fin (voir api/server.py). Les horodatages
    restent fidèles à quand chaque étape a réellement eu lieu, mais
    l'affichage arrive en rafale, pas au fil de l'eau.
    """
    return {
        "type": "activity",
        "kind": kind,
        "text": text,
        "source_agent": DEFAULT_SOURCE_AGENT,
    }


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


def read_user_image(data: dict) -> str:
    """
    Extrait l'image base64 d'un message entrant de type « image ».

    Photo envoyée par le téléphone (pont mobile, Phase 4) pour alimenter
    le pipeline vision existant (OCR, VLM si activé) — voir
    VISION_LONG_TERME.md §2 Pilier 3. Un seul champ, « image_base64 »,
    même logique que read_user_audio().
    """
    if not isinstance(data, dict):
        return ""
    value = data.get("image_base64")
    return value.strip() if isinstance(value, str) and value.strip() else ""
