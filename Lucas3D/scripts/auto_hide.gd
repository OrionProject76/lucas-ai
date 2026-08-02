extends Node

@export var hide_delay: float = 2.0
@export var show_zone_height: int = 100
@export var hide_zone_height: int = 200

var hide_timer: float = 0.0
var is_hidden: bool = false

func _ready():
    print("AutoHide initialise")

func _process(delta: float):
    if not Global.auto_hide_enabled:
        if is_hidden:
            _show()
        return
    var mouse_pos = DisplayServer.mouse_get_position()
    var screen = DisplayServer.screen_get_size()
    var mouse_in_show_zone = mouse_pos.y > screen.y - show_zone_height
    var mouse_in_hide_zone = mouse_pos.y < hide_zone_height
    if mouse_in_show_zone and is_hidden:
        _show()
        hide_timer = 0.0
    elif not mouse_in_show_zone and not is_hidden:
        hide_timer += delta
        if hide_timer >= hide_delay:
            _hide()
            hide_timer = 0.0
    elif mouse_in_show_zone:
        hide_timer = 0.0

func _hide():
    if is_hidden:
        return
    is_hidden = true
    var tween = create_tween()
    tween.tween_property(get_window(), "position:y", -50, 0.4)
    print("Lucas3D masque")

func _show():
    if not is_hidden:
        return
    is_hidden = false
    var tween = create_tween()
    tween.tween_property(get_window(), "position:y", 0, 0.4)
    print("Lucas3D visible")
