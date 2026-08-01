extends Node3D

@onready var eye_left: MeshInstance3D = $EyeLeft
@onready var eye_right: MeshInstance3D = $EyeRight
@onready var mouth: MeshInstance3D = $Mouth
@onready var blink_timer: Timer = $BlinkTimer
@onready var speak_timer: Timer = $SpeakTimer

var original_eye_scale: Vector3
var is_blinking: bool = false
var mouth_target_scale: float = 1.0
var mouth_current_scale: float = 1.0
var eye_look_offset: Vector2 = Vector2.ZERO

func _ready():
    original_eye_scale = eye_left.scale
    blink_timer.timeout.connect(_on_blink)
    speak_timer.timeout.connect(_on_speak_tick)
    Global.orion_speaking.connect(_on_orion_speaking)
    Global.orion_idle.connect(_on_orion_idle)

func set_eye_look(normalized_pos: Vector2):
    eye_look_offset = normalized_pos * 0.08

func _process(delta: float):
    var target_pos_left = Vector3(-0.95 + eye_look_offset.x, 0.55 + eye_look_offset.y, 2.05)
    var target_pos_right = Vector3(0.95 + eye_look_offset.x, 0.55 + eye_look_offset.y, 2.05)
    eye_left.position = eye_left.position.lerp(target_pos_left, delta * 5.0)
    eye_right.position = eye_right.position.lerp(target_pos_right, delta * 5.0)
    mouth_current_scale = lerp(mouth_current_scale, mouth_target_scale, delta * 15.0)
    mouth.scale = Vector3(1.0, mouth_current_scale, 1.0)
    if is_blinking:
        var blink_progress = 1.0 - (blink_timer.time_left / 0.15)
        var eye_scale_y = original_eye_scale.y * abs(sin(blink_progress * 3.14159))
        eye_left.scale = Vector3(original_eye_scale.x, max(eye_scale_y, 0.05), original_eye_scale.z)
        eye_right.scale = Vector3(original_eye_scale.x, max(eye_scale_y, 0.05), original_eye_scale.z)
    else:
        eye_left.scale = eye_left.scale.lerp(original_eye_scale, delta * 10.0)
        eye_right.scale = eye_right.scale.lerp(original_eye_scale, delta * 10.0)

func _on_blink():
    is_blinking = true
    blink_timer.wait_time = randf_range(2.0, 5.0)
    blink_timer.start()
    await get_tree().create_timer(0.15).timeout
    is_blinking = false

func _on_speak_tick():
    if Global.orion_state == "speaking" and AudioVisualizer:
        var intensity = AudioVisualizer.get_speech_intensity()
        mouth_target_scale = 0.3 + intensity * 2.5
        mouth_target_scale = clamp(mouth_target_scale, 0.3, 2.5)
    else:
        mouth_target_scale = 1.0

func _on_orion_speaking(intensity: float):
    mouth_target_scale = 0.3 + intensity * 2.0

func _on_orion_idle():
    mouth_target_scale = 1.0
