extends Node3D

# ── Expressions et vie du visage ──────────────────────────────────────
#
# Avant : un clignement, une bouche qui s'ouvre, et un suivi de souris
# d'amplitude 0.08 — invisible. Le regard etait fixe, et aucune
# expression ne distinguait « je reflechis » de « je te regarde ».
#
# Deux ajouts portent l'essentiel de l'effet « vivant » :
#
#   1. UNE TABLE ETAT -> POSE. Chaque etat definit l'ouverture des yeux,
#      leur inclinaison, la largeur de la bouche et l'inclinaison de la
#      tete. Le passage d'un etat a l'autre se fait en lerp.
#
#   2. DES MICRO-SACCADES. De petits sauts du regard toutes les 0,4 a
#      2,2 s. C'est l'indice de vie le plus fort d'un visage : un oeil
#      parfaitement immobile se lit immediatement comme mort, meme quand
#      tout le reste bouge. Et ca ne coute rien.
#
# Voir VISION_LONG_TERME.md — « avatar vivant, pas robotique ».

@onready var eye_left: MeshInstance3D = $EyeLeft
@onready var eye_right: MeshInstance3D = $EyeRight
@onready var mouth: MeshInstance3D = $Mouth
@onready var blink_timer: Timer = $BlinkTimer
@onready var speak_timer: Timer = $SpeakTimer

# Poses par etat. Les valeurs sont volontairement faibles : une
# expression se lit a l'ecart, pas a l'amplitude.
const POSES := {
    "idle":     {"eye": 1.0,  "tilt": 0.0,   "mouth": 1.0,  "head": 0.0},
    # Yeux plisses, tete penchee : la concentration.
    "thinking": {"eye": 0.72, "tilt": 0.10,  "mouth": 0.7,  "head": 0.13},
    # Yeux plus ouverts, tete droite : l'attention portee vers Cyril.
    "speaking": {"eye": 1.08, "tilt": -0.04, "mouth": 1.0,  "head": -0.03},
    # Grands yeux, tete inclinee de l'autre cote : la curiosite.
    "watching": {"eye": 1.18, "tilt": -0.09, "mouth": 0.85, "head": -0.10},
}

const POSE_LERP := 2.5          # transition d'etat, ~0,4 s
const SACCADE_MIN := 0.4
const SACCADE_MAX := 2.2
const SACCADE_RANGE := 0.22     # amplitude d'un saut de regard
const LOOK_RANGE := 0.30        # suivi de souris (etait 0.08, invisible)
const LOOK_LERP := 6.0

# ⚠️ LES YEUX DOIVENT SUIVRE LA COURBURE DE LA TETE.
# Ils etaient a un z FIXE (2.0) alors que la tete est un ellipsoide : des
# qu'une saccade les decalait lateralement, l'un ressortait et l'autre
# s'enfoncait. Visible sur la planche des quatre expressions — l'oeil
# gauche paraissait systematiquement plus gros et plus clair que le droit.
# Calcul : a x = -1.2 la surface est a z = 1.95 ; a x = -1.42 elle tombe a
# 1.82, soit 13 centiemes d'ecart d'enfoncement pour un simple regard de
# cote.
# Demi-axes de l'ellipsoide : Head est une sphere de rayon 2.5 mise a
# l'echelle (1.0, 1.08, 0.92) — voir face_root.tscn.
const HEAD_A := 2.5      # demi-axe X
const HEAD_B := 2.7      # demi-axe Y
const HEAD_C := 2.3      # demi-axe Z
const EYE_PROUD := 0.06  # de combien l'oeil depasse la surface

var eye_base_left: Vector3
var eye_base_right: Vector3
var eye_base_scale: Vector3
var mouth_base_scale: Vector3

var is_blinking: bool = false
var mouth_target_scale: float = 1.0
var mouth_current_scale: float = 1.0

var eye_look_offset: Vector2 = Vector2.ZERO
var saccade_offset: Vector2 = Vector2.ZERO
var saccade_current: Vector2 = Vector2.ZERO
var saccade_timer: float = 0.0

var pose_eye: float = 1.0
var pose_tilt: float = 0.0
var pose_mouth: float = 1.0
var pose_head: float = 0.0


func _ready():
    eye_base_left = eye_left.position
    eye_base_right = eye_right.position
    eye_base_scale = eye_left.scale
    mouth_base_scale = mouth.scale
    blink_timer.timeout.connect(_on_blink)
    speak_timer.timeout.connect(_on_speak_tick)
    Global.lucas_speaking.connect(_on_lucas_speaking)
    Global.lucas_idle.connect(_on_lucas_idle)
    _programmer_saccade()


func set_eye_look(normalized_pos: Vector2):
    eye_look_offset = normalized_pos * LOOK_RANGE


func _programmer_saccade():
    saccade_timer = randf_range(SACCADE_MIN, SACCADE_MAX)
    # Un saut de regard est bref et brusque : la cible change d'un coup,
    # c'est le lerp qui l'adoucit juste ce qu'il faut.
    saccade_offset = Vector2(
        randf_range(-1.0, 1.0), randf_range(-0.6, 0.6)
    ) * SACCADE_RANGE


func _process(delta: float):
    _maj_pose(delta)
    _maj_saccades(delta)
    _maj_yeux(delta)
    _maj_bouche(delta)


func _maj_pose(delta: float):
    var p: Dictionary = POSES.get(Global.lucas_state, POSES["idle"])
    pose_eye = lerp(pose_eye, float(p["eye"]), delta * POSE_LERP)
    pose_tilt = lerp(pose_tilt, float(p["tilt"]), delta * POSE_LERP)
    pose_mouth = lerp(pose_mouth, float(p["mouth"]), delta * POSE_LERP)
    pose_head = lerp(pose_head, float(p["head"]), delta * POSE_LERP)
    # ⚠️ Uniquement Z : main.gd pilote deja X et Y de FaceRoot pour la
    # derive. Toucher aux trois ici ferait se battre les deux systemes.
    rotation.z = pose_head


func _maj_saccades(delta: float):
    saccade_timer -= delta
    if saccade_timer <= 0.0:
        _programmer_saccade()
    saccade_current = saccade_current.lerp(saccade_offset, delta * 12.0)


func _z_surface(x: float, y: float) -> float:
    """Profondeur de la surface de la tete a cette position frontale."""
    var reste := 1.0 - pow(x / HEAD_A, 2.0) - pow(y / HEAD_B, 2.0)
    return HEAD_C * sqrt(max(reste, 0.0)) + EYE_PROUD


func _maj_yeux(delta: float):
    var decalage := eye_look_offset + saccade_current
    var xg := eye_base_left.x + decalage.x
    var xd := eye_base_right.x + decalage.x
    var yy := eye_base_left.y + decalage.y
    var cible_g := Vector3(xg, yy, _z_surface(xg, yy))
    var cible_d := Vector3(xd, yy, _z_surface(xd, yy))
    eye_left.position = eye_left.position.lerp(cible_g, delta * LOOK_LERP)
    eye_right.position = eye_right.position.lerp(cible_d, delta * LOOK_LERP)

    # Inclinaison OPPOSEE des deux yeux : c'est elle qui fait lire une
    # expression plutot qu'une paire de points.
    eye_left.rotation.z = lerp(eye_left.rotation.z, pose_tilt, delta * POSE_LERP)
    eye_right.rotation.z = lerp(eye_right.rotation.z, -pose_tilt, delta * POSE_LERP)

    var ouverture := pose_eye
    if is_blinking:
        var t := 1.0 - (blink_timer.time_left / 0.15)
        ouverture *= abs(sin(t * PI))
    var cible_echelle := Vector3(
        eye_base_scale.x, max(eye_base_scale.y * ouverture, 0.04), eye_base_scale.z
    )
    var vitesse := 22.0 if is_blinking else 9.0
    eye_left.scale = eye_left.scale.lerp(cible_echelle, delta * vitesse)
    eye_right.scale = eye_right.scale.lerp(cible_echelle, delta * vitesse)


func _maj_bouche(delta: float):
    mouth_current_scale = lerp(mouth_current_scale, mouth_target_scale, delta * 15.0)
    mouth.scale = Vector3(
        mouth_base_scale.x * pose_mouth,
        mouth_base_scale.y * mouth_current_scale,
        mouth_base_scale.z
    )


func _on_blink():
    is_blinking = true
    blink_timer.wait_time = randf_range(2.0, 5.0)
    blink_timer.start()
    await get_tree().create_timer(0.15).timeout
    is_blinking = false


func _on_speak_tick():
    if Global.lucas_state == "speaking" and AudioVisualizer:
        var intensity = AudioVisualizer.get_speech_intensity()
        mouth_target_scale = clamp(0.3 + intensity * 2.5, 0.3, 2.5)
    else:
        mouth_target_scale = 1.0


func _on_lucas_speaking(intensity: float):
    mouth_target_scale = 0.3 + intensity * 2.0


func _on_lucas_idle():
    mouth_target_scale = 1.0
