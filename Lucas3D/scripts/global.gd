extends Node

signal main_ready
signal lucas_speaking(intensity: float)
signal lucas_idle
signal system_data_updated(cpu: float, ram: float, gpu: float)
signal chat_message_received(text: String, from_lucas: bool)

# État de présence complet, tel que l'émet l'API (api/protocol.py).
# lucas_speaking et lucas_idle ne couvrent que deux des cinq états ;
# thinking, watching et listening n'avaient aucun moyen d'atteindre le
# visage 3D. Ce signal les transporte tous, sans casser les deux autres
# auxquels face_controller.gd est déjà branché.
signal lucas_state_changed(state: String)

var is_visible: bool = true
var click_through: bool = false
# ⚠️ Désactivé par défaut : incohérent avec la fenêtre plein écran.
# auto_hide._hide() déplace la fenêtre à y = -50, ce qui masquait 50 px
# d'une fenêtre de 2160 — un geste écrit pour une barre de 50 px de haut,
# pas pour un calque plein écran. Et la zone qui la fait réapparaître ne
# fait que 100 px en bas de l'écran, donc l'avatar se « masquait » au
# bout de 2 s dès que la souris était ailleurs.
# Sur un calque transparent et cliquable-au-travers, masquer se fait en
# estompant le contenu, pas en bougeant la fenêtre. À revoir avec le
# chantier UI. Bascule par F10 en jeu.
var auto_hide_enabled: bool = false
var lucas_state: String = "idle"

func _ready():
    print("Global singleton initialise")
