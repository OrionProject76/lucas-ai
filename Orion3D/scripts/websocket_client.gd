extends Node

# Canal unique vers Luca's — l'API FastAPI, et non plus le service
# orion3d_bridge.py supprimé le 01/08/2026.
#
# Ce bridge était un simple écho : il répétait les messages sans jamais
# passer par Ollama. Pire, il ne démarrait plus du tout, son handler
# ayant une signature obsolète depuis websockets 12.
#
# Passer par l'API donne à l'avatar 3D ce que le bridge court-circuitait :
# le routage local/cloud, les gardes de sensibilité, la mémoire
# persistante. Le vocabulaire des messages est défini dans
# api/protocol.py, côté Python.
#
# ⚠️ 127.0.0.1 et non localhost : l'API n'écoute que sur la boucle
# locale, sans authentification (voir config.py, décision du 01/08).
@export var websocket_url: String = "ws://127.0.0.1:8000/ws"
@export var reconnect_interval: float = 3.0

var socket: WebSocketPeer
var connected: bool = false
var reconnect_timer: float = 0.0

func _ready():
    _connect_to_server()
    Global.main_ready.connect(_on_main_ready)

func _on_main_ready():
    print("WebSocket pret sur ", websocket_url)

func _process(delta: float):
    if socket:
        socket.poll()
        var state = socket.get_ready_state()
        match state:
            WebSocketPeer.STATE_OPEN:
                if not connected:
                    connected = true
                    print("Connecte a Orion Backend")
                    _send_heartbeat()
                while socket.get_available_packets() > 0:
                    _handle_message(socket.get_packet().get_string_from_utf8())
            WebSocketPeer.STATE_CLOSED:
                if connected:
                    connected = false
                    print("Deconnecte")
                _reconnect_timer(delta)
            WebSocketPeer.STATE_CONNECTING:
                pass

func _connect_to_server():
    socket = WebSocketPeer.new()
    var err = socket.connect_to_url(websocket_url)
    if err != OK:
        print("Erreur connexion : ", err)
    else:
        print("Connexion en cours...")

func _reconnect_timer(delta: float):
    reconnect_timer += delta
    if reconnect_timer >= reconnect_interval:
        reconnect_timer = 0.0
        print("Reconnexion...")
        _connect_to_server()

func _handle_message(msg: String):
    var json = JSON.new()
    var err = json.parse(msg)
    if err != OK:
        return
    var data = json.get_data()
    if data is Dictionary:
        match data.get("type", ""):
            "avatar_state":
                _apply_state(data.get("state", "idle"), data.get("text", ""))
            "chat":
                Global.chat_message_received.emit(data.get("text", ""), data.get("from_orion", true))
            "system":
                Global.system_data_updated.emit(data.get("cpu", 0.0), data.get("ram", 0.0), data.get("gpu", 0.0))
            "error":
                Global.chat_message_received.emit("[Erreur] " + str(data.get("detail", "")), true)
            # « speak » et « idle » étaient le vocabulaire du bridge
            # supprimé. Conservés le temps que d'éventuels clients tiers
            # migrent ; l'API n'émet plus que « avatar_state ».
            "speak":
                _apply_state("speaking", "")
            "idle":
                _apply_state("idle", "")
            "show":
                WindowManager.toggle_visibility()
            "hide":
                WindowManager.toggle_visibility()

# Traduit un état de présence en signaux du bus Global.
#
# Les cinq états sont ceux de l'avatar PySide6 : une seule liste pour les
# deux interfaces, sinon elles divergent (un test Python le vérifie).
# thinking, watching et listening n'ont pas encore d'animation propre au
# visage 3D — ils sont diffusés sur orion_state_changed pour que
# face_controller puisse s'en saisir, sans forcer la bouche à bouger
# comme si Luca's parlait.
func _apply_state(state: String, text: String):
    Global.orion_state = state
    Global.orion_state_changed.emit(state)

    match state:
        "speaking":
            Global.orion_speaking.emit(0.8)
            if text != "":
                Global.chat_message_received.emit(text, true)
        "idle":
            Global.orion_idle.emit()
        _:
            # thinking / watching / listening : le visage cesse de parler
            # sans repasser en repos complet.
            Global.orion_idle.emit()

func send_message(data: Dictionary):
    if connected and socket:
        socket.send_text(JSON.stringify(data))

func _send_heartbeat():
    send_message({"type": "hello", "client": "orion3d_godot", "version": "1.0"})
