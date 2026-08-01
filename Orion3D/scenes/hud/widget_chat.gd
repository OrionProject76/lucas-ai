extends VBoxContainer

@onready var messages_container: VBoxContainer = $Scroll/Messages

var message_scene = preload("res://scenes/hud/chat_message.tscn")

func _ready():
    Global.chat_message_received.connect(_add_message)

func _add_message(text: String, from_orion: bool):
    var msg = message_scene.instantiate()
    msg.set_message(text, from_orion)
    messages_container.add_child(msg)
    await get_tree().process_frame
    $Scroll.scroll_vertical = $Scroll.get_v_scroll_bar().max_value
    while messages_container.get_child_count() > 50:
        messages_container.get_child(0).queue_free()
