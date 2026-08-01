extends Node

var window: Window
var screen_size: Vector2i

func _ready():
    window = get_window()
    screen_size = DisplayServer.screen_get_size()

func setup_window():
    if not window:
        return
    window.borderless = true
    window.transparent = true
    window.unresizable = true
    window.always_on_top = true
    window.size = screen_size
    window.position = Vector2i(0, 0)
    DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_TRANSPARENT, true, window.get_window_id())
    DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, true, window.get_window_id())
    DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, true, window.get_window_id())
    DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_NO_FOCUS, true, window.get_window_id())
    _set_click_through(false)
    print("Fenetre configuree : " + str(screen_size))

func _set_click_through(enabled: bool):
    Global.click_through = enabled
    var win_id = window.get_window_id()
    if enabled:
        DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_NO_FOCUS, true, win_id)
        var center = Vector2(screen_size.x / 2, screen_size.y / 2)
        var radius = 200
        var polygon = PackedVector2Array()
        for i in range(32):
            var angle = i * 3.14159 * 2 / 32
            polygon.append(center + Vector2(cos(angle), sin(angle)) * radius)
        DisplayServer.window_set_mouse_passthrough(polygon, win_id)
    else:
        DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_NO_FOCUS, false, win_id)
        DisplayServer.window_set_mouse_passthrough(PackedVector2Array(), win_id)

func toggle_click_through():
    _set_click_through(not Global.click_through)
    print("Click-through : " + ("ON" if Global.click_through else "OFF"))

func toggle_visibility():
    Global.is_visible = not Global.is_visible
    if Global.is_visible:
        window.show()
        var tween = create_tween()
        tween.tween_property(window, "modulate:a", 1.0, 0.5)
    else:
        var tween = create_tween()
        tween.tween_property(window, "modulate:a", 0.0, 0.3)
        tween.tween_callback(window.hide)

func _input(event):
    if event is InputEventKey and event.pressed and not event.echo:
        match event.keycode:
            KEY_F12:
                toggle_click_through()
            KEY_F11:
                toggle_visibility()
            KEY_F10:
                Global.auto_hide_enabled = not Global.auto_hide_enabled
                print("Auto-hide : " + ("ON" if Global.auto_hide_enabled else "OFF"))
