extends Control

@onready var input_field: LineEdit = $BottomBar/Input
@onready var status_label: Label = $TopBar/Status

func _ready():
    Global.system_data_updated.connect(_on_system_updated)
    Global.chat_message_received.connect(_on_chat_received)
    print("HUD Manager pret")

func _on_input_submitted(text: String):
    if text.strip_edges() == "":
        return
    input_field.clear()
    Global.chat_message_received.emit(text, false)
    WebSocketClient.send_message({"type": "chat", "text": text, "source": "user"})

func _on_system_updated(cpu: float, ram: float, gpu: float):
    status_label.text = "CPU: %.0f%% | RAM: %.0f%% | GPU: %.0f%%" % [cpu, ram, gpu]

func _on_chat_received(text: String, from_lucas: bool):
    pass
