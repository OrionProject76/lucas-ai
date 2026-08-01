extends Node

@export var websocket_url: String = "ws://localhost:8765"
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
            "chat":
                Global.chat_message_received.emit(data.get("text", ""), data.get("from_orion", true))
            "speak":
                Global.orion_speaking.emit(data.get("intensity", 0.5))
                Global.orion_state = "speaking"
            "idle":
                Global.orion_idle.emit()
                Global.orion_state = "idle"
            "system":
                Global.system_data_updated.emit(data.get("cpu", 0.0), data.get("ram", 0.0), data.get("gpu", 0.0))
            "show":
                WindowManager.toggle_visibility()
            "hide":
                WindowManager.toggle_visibility()

func send_message(data: Dictionary):
    if connected and socket:
        socket.send_text(JSON.stringify(data))

func _send_heartbeat():
    send_message({"type": "hello", "client": "orion3d_godot", "version": "1.0"})
