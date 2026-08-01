extends Node3D

@onready var face_root: Node3D = $FaceRoot

func _ready():
    print("Orion3D Desktop Pal demarre")
    _force_fullscreen()
    WindowManager.setup_window()
    Global.main_ready.emit()

func _force_fullscreen():
    var win = get_window()
    var screen = DisplayServer.screen_get_size()
    win.borderless = true
    win.transparent = true
    win.unresizable = true
    win.always_on_top = true
    win.size = screen
    win.position = Vector2i(0, 0)
    DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_TRANSPARENT, true, win.get_window_id())
    DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, true, win.get_window_id())
    DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, true, win.get_window_id())
    DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_NO_FOCUS, true, win.get_window_id())
    print("Fenetre forcee : " + str(screen))

func _process(delta: float):
    _handle_face_float(delta)
    _handle_eye_tracking()

func _handle_face_float(delta: float):
    var t = Time.get_time_dict_from_system()
    var sec = float(t["second"]) + float(Time.get_ticks_msec() % 1000) / 1000.0
    var float_x = sin(sec * 0.7) * 0.25
    var float_y = sin(sec * 0.5 + 1.0) * 0.20 + cos(sec * 0.3) * 0.15
    var float_z = sin(sec * 0.4 + 2.0) * 0.10
    var rot_x = sin(sec * 0.6) * 0.08
    var rot_y = cos(sec * 0.4) * 0.12
    var rot_z = sin(sec * 0.3) * 0.05
    face_root.position = Vector3(float_x, float_y, float_z)
    face_root.rotation = Vector3(rot_x, rot_y, rot_z)

func _handle_eye_tracking():
    var viewport = get_viewport()
    if viewport:
        var mouse_pos = viewport.get_mouse_position()
        var viewport_size = viewport.get_visible_rect().size
        var normalized = (mouse_pos - viewport_size / 2.0) / (viewport_size / 2.0)
        if face_root.has_method("set_eye_look"):
            face_root.set_eye_look(normalized)
