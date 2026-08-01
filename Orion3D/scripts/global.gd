extends Node

signal main_ready
signal orion_speaking(intensity: float)
signal orion_idle
signal system_data_updated(cpu: float, ram: float, gpu: float)
signal chat_message_received(text: String, from_orion: bool)

var is_visible: bool = true
var click_through: bool = false
var auto_hide_enabled: bool = true
var orion_state: String = "idle"

func _ready():
    print("Global singleton initialise")
