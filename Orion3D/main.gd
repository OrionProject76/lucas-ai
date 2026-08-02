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

# ── Dérive libre de l'avatar ──────────────────────────────────────────
#
# ⚠️ L'ANCIEN FLOTTEMENT SE TÉLÉPORTAIT UNE FOIS PAR MINUTE. Il lisait
# Time.get_time_dict_from_system()["second"], qui va de 0 à 59 puis
# repasse à 0 : sin(59 * 0.7) et sin(0) n'ont aucun rapport, donc la
# position sautait à chaque minute pleine. La partie fractionnaire
# (get_ticks_msec() % 1000) n'était pas non plus synchronisée sur la
# seconde horloge, ce qui ajoutait un saut à l'intérieur de chaque
# seconde. D'où un accumulateur de delta : monotone, sans repli.
var drift_time: float = 0.0

# Périodes en secondes, volontairement NON harmoniques. Leur plus petit
# commun multiple est énorme, donc le motif ne se répète pas de façon
# perceptible — sans avoir besoin de vrai hasard, ce qui garde le
# mouvement reproductible et sans à-coup.
const DRIFT_PERIODS_X := [170.0, 103.0]
const DRIFT_PERIODS_Y := [270.0, 146.0]
const DRIFT_WEIGHTS := [0.6, 0.4]

# Demi-encombrement de la tête (SphereMesh : radius 2.5, height 4.0) et
# marge de sécurité, en unités 3D.
const HEAD_HALF_X := 2.5
const HEAD_HALF_Y := 2.0
const DRIFT_MARGIN := 0.5

# Part de l'espace libre réellement parcourue. X est plus restreint pour
# que l'avatar ne passe pas sous les panneaux SYSTEME et CONVERSATION.
const DRIFT_ZONE_X := 0.7
const DRIFT_ZONE_Y := 0.85

# Quand Luca's parle ou réfléchit, elle se pose : c'est ce que fait
# quelqu'un qui s'adresse à vous. Signal visuel gratuit — on voit qu'elle
# écoute avant même de lire le texte — et le texte affiché près d'elle ne
# part pas à la dérive pendant qu'on le lit. Décision de Cyril, 02/08/2026.
const ATTENTION_DRIFT_SCALE := 0.3
const ATTENTION_LERP_SPEED := 1.0 / 1.5   # transition sur ~1,5 s
var attention: float = 1.0

# Respiration : rapide et de faible amplitude, par-dessus la dérive.
const BREATH_PERIOD := 4.0
const BREATH_AMPLITUDE := 0.12


func _process(delta: float):
    _handle_face_float(delta)
    _handle_eye_tracking()


func _drift_amplitude() -> Vector2:
    """
    Zone de dérive, DÉRIVÉE du frustum — jamais codée en dur.

    Si la caméra, le champ de vision ou la résolution changent, la zone
    suit toute seule. C'est ce qui permet de régler la taille de l'avatar
    sans avoir à retoucher son déplacement.
    """
    var cam := $Camera3D as Camera3D
    if cam == null:
        return Vector2.ZERO
    # L'avatar vit au plan z ≈ 0 ; la distance utile est donc celle de la
    # caméra à ce plan.
    var distance: float = abs(cam.position.z)
    var half_h: float = distance * tan(deg_to_rad(cam.fov) * 0.5)
    var vp: Vector2 = get_viewport().get_visible_rect().size
    var aspect: float = vp.x / max(vp.y, 1.0)
    var half_w: float = half_h * aspect
    return Vector2(
        max(0.0, (half_w - HEAD_HALF_X - DRIFT_MARGIN) * DRIFT_ZONE_X),
        max(0.0, (half_h - HEAD_HALF_Y - DRIFT_MARGIN) * DRIFT_ZONE_Y)
    )


func _layered_wave(periods: Array, phase: float) -> float:
    var total: float = 0.0
    for i in periods.size():
        total += DRIFT_WEIGHTS[i] * sin(TAU * drift_time / periods[i] + phase * float(i + 1))
    return total


func _handle_face_float(delta: float):
    drift_time += delta

    # L'état vient du backend via WebSocket (api/protocol.py).
    var cible: float = 1.0 if Global.orion_state == "idle" else ATTENTION_DRIFT_SCALE
    attention = move_toward(attention, cible, ATTENTION_LERP_SPEED * delta)

    var amp: Vector2 = _drift_amplitude() * attention
    var drift_x: float = amp.x * _layered_wave(DRIFT_PERIODS_X, 0.0)
    var drift_y: float = amp.y * _layered_wave(DRIFT_PERIODS_Y, 1.3)

    # Respiration : indépendante de l'attention, elle ne s'arrête jamais.
    var breath: float = sin(TAU * drift_time / BREATH_PERIOD) * BREATH_AMPLITUDE

    face_root.position = Vector3(drift_x, drift_y + breath, sin(TAU * drift_time / 61.0) * 0.4)
    face_root.rotation = Vector3(
        sin(TAU * drift_time / 89.0) * 0.06 * attention,
        sin(TAU * drift_time / 67.0) * 0.10 * attention,
        sin(TAU * drift_time / 113.0) * 0.04 * attention
    )


func _handle_eye_tracking():
    var viewport = get_viewport()
    if viewport:
        var mouse_pos = viewport.get_mouse_position()
        var viewport_size = viewport.get_visible_rect().size
        var normalized = (mouse_pos - viewport_size / 2.0) / (viewport_size / 2.0)
        if face_root.has_method("set_eye_look"):
            face_root.set_eye_look(normalized)
