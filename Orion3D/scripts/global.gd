extends Node

signal main_ready
signal orion_speaking(intensity: float)
signal orion_idle
signal system_data_updated(cpu: float, ram: float, gpu: float)
signal chat_message_received(text: String, from_orion: bool)

# État de présence complet, tel que l'émet l'API (api/protocol.py).
# orion_speaking et orion_idle ne couvrent que deux des cinq états ;
# thinking, watching et listening n'avaient aucun moyen d'atteindre le
# visage 3D. Ce signal les transporte tous, sans casser les deux autres
# auxquels face_controller.gd est déjà branché.
signal orion_state_changed(state: String)

var is_visible: bool = true
var click_through: bool = false
var auto_hide_enabled: bool = true
var orion_state: String = "idle"

func _ready():
    print("Global singleton initialise")
