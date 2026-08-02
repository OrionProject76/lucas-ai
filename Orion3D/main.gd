extends Node3D

@onready var face_root: Node3D = $FaceRoot

func _ready():
    _setup_noise()
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

# ── Dérive organique de l'avatar ──────────────────────────────────────
#
# ⚠️ POURQUOI LES SINUSOÏDES SEULES DONNAIENT UN MOUVEMENT ROBOTIQUE.
# Les périodes allaient de 103 à 270 s. Sur une fenêtre de 4 secondes on
# observe 2,4 % d'un cycle — et sur 2,4 % d'une sinusoïde la dérivée est
# constante. C'était une droite à vitesse constante PAR CONSTRUCTION.
# Des fréquences non harmoniques décorrèlent le motif à long terme mais
# n'apportent AUCUNE énergie aux échelles courtes. Le défaut n'était pas
# « pas assez d'aléatoire » : c'était l'absence totale de contenu entre
# 1 et 8 secondes.
#
# Deux mécanismes le corrigent, et ils sont complémentaires :
#   1. du bruit fractal (fBm), qui a de l'énergie à TOUTES les échelles
#   2. une déformation du temps, qui crée pauses et accélérations
#
# Voir VISION_LONG_TERME.md — « mouvements organiques, pas mécaniques ».

# Graines fixes : le mouvement est reproductible d'un lancement à
# l'autre, donc mesurable. « Organique » ne veut pas dire « intestable ».
const SEED_MACRO_X := 1101
const SEED_MACRO_Y := 2027
const SEED_MICRO_X := 3313
const SEED_MICRO_Y := 4507
const SEED_SPEED := 5821

# Périodes de base, en secondes. La macro porte les longues traversées ;
# la micro est celle qui casse la ligne droite sur quelques secondes.
const MACRO_PERIOD := 90.0
const MICRO_PERIOD := 7.0
const SPEED_PERIOD := 25.0

# Le fBm dépasse rarement ±0.6 : le gain récupère la plage utile. La
# micro reste minoritaire — elle irrégularise, elle ne pilote pas.
const MACRO_GAIN := 1.7
const MICRO_GAIN := 0.22

# Déformation du temps. À 0.08 l'avatar s'immobilise presque — une vraie
# pause ; à 1.9 il file. Comme la déformation porte sur l'horloge
# PARTAGÉE, la pause est cohérente sur les deux axes : il s'arrête
# entièrement, ce qui se lit comme de l'attention. Une pause sur un seul
# axe se lirait comme un bug.
const SPEED_MIN := 0.08
const SPEED_MAX := 1.9

var noise_macro_x := FastNoiseLite.new()
var noise_macro_y := FastNoiseLite.new()
var noise_micro_x := FastNoiseLite.new()
var noise_micro_y := FastNoiseLite.new()
var noise_speed := FastNoiseLite.new()

# Deux horloges. `drift_time` est DÉFORMÉE (elle ralentit et accélère).
# `warp_clock` avance à vitesse constante et sert à échantillonner la
# vitesse elle-même — sinon une pause figerait aussi la vitesse, et
# l'avatar ne repartirait jamais.
var drift_time: float = 0.0
var warp_clock: float = 0.0

# Demi-encombrement de la tête. ⚠️ Suit SphereMesh_head : radius 2.5,
# height 5.0 — une VRAIE sphère. Elle valait height 4.0, soit 5.0 de
# large pour 4.0 de haut : un sphéroïde aplati de 25 %, ce que Cyril a vu
# comme un « œuf ».
const HEAD_HALF_X := 2.5
const HEAD_HALF_Y := 2.5
const DRIFT_MARGIN := 0.5

# Part de l'espace libre réellement parcourue. X est plus restreint pour
# que l'avatar ne passe pas sous les panneaux SYSTEME et CONVERSATION.
# ⚠️ 0.7 ne suffisait pas : mesuré sur 5 minutes de fonctionnement réel,
# l'avatar chevauchait les deux panneaux.
const DRIFT_ZONE_X := 0.5
const DRIFT_ZONE_Y := 0.85

# Quand Luca's parle ou réfléchit, elle se pose. Décision de Cyril.
const ATTENTION_DRIFT_SCALE := 0.3
const ATTENTION_LERP_SPEED := 1.0 / 1.5
var attention: float = 1.0

# La respiration garde une horloge NON déformée : elle ne s'arrête
# jamais. C'est elle qui garde l'avatar vivant pendant qu'il est
# immobile — tout figer serait un gel, pas un repos.
const BREATH_PERIOD := 4.0
const BREATH_AMPLITUDE := 0.12


func _setup_noise():
    var config := [
        [noise_macro_x, SEED_MACRO_X, MACRO_PERIOD, 4],
        [noise_macro_y, SEED_MACRO_Y, MACRO_PERIOD, 4],
        [noise_micro_x, SEED_MICRO_X, MICRO_PERIOD, 3],
        [noise_micro_y, SEED_MICRO_Y, MICRO_PERIOD, 3],
        [noise_speed, SEED_SPEED, SPEED_PERIOD, 3],
    ]
    for c in config:
        var n: FastNoiseLite = c[0]
        n.seed = c[1]
        n.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
        n.fractal_type = FastNoiseLite.FRACTAL_FBM
        n.fractal_octaves = c[3]
        # Chaque octave double la fréquence : à 4 octaves, une base de
        # 90 s descend jusqu'à ~11 s ; la micro à 7 s descend à ~1,75 s.
        n.frequency = 1.0 / c[2]


func _process(delta: float):
    _handle_face_float(delta)
    _handle_eye_tracking()


func _drift_amplitude() -> Vector2:
    """
    Zone de dérive, DÉRIVÉE du frustum — jamais codée en dur.

    Si la caméra, le champ de vision ou la résolution changent, la zone
    suit toute seule.
    """
    var cam := $Camera3D as Camera3D
    if cam == null:
        return Vector2.ZERO
    var distance: float = abs(cam.position.z)
    var half_h: float = distance * tan(deg_to_rad(cam.fov) * 0.5)
    var vp: Vector2 = get_viewport().get_visible_rect().size
    var aspect: float = vp.x / max(vp.y, 1.0)
    var half_w: float = half_h * aspect
    return Vector2(
        max(0.0, (half_w - HEAD_HALF_X - DRIFT_MARGIN) * DRIFT_ZONE_X),
        max(0.0, (half_h - HEAD_HALF_Y - DRIFT_MARGIN) * DRIFT_ZONE_Y)
    )


func _drift_speed() -> float:
    """Vitesse d'écoulement du temps : pauses et accélérations."""
    var raw: float = clamp(noise_speed.get_noise_1d(warp_clock) * 1.8, -1.0, 1.0)
    return lerp(SPEED_MIN, SPEED_MAX, (raw + 1.0) * 0.5)


func _drift_offset() -> Vector2:
    """Position normalisée dans [-1, 1], macro + micro."""
    return Vector2(
        clamp(noise_macro_x.get_noise_1d(drift_time) * MACRO_GAIN
            + noise_micro_x.get_noise_1d(drift_time) * MICRO_GAIN, -1.0, 1.0),
        clamp(noise_macro_y.get_noise_1d(drift_time) * MACRO_GAIN
            + noise_micro_y.get_noise_1d(drift_time) * MICRO_GAIN, -1.0, 1.0)
    )


func _handle_face_float(delta: float):
    warp_clock += delta
    drift_time += delta * _drift_speed()

    var cible: float = 1.0 if Global.orion_state == "idle" else ATTENTION_DRIFT_SCALE
    attention = move_toward(attention, cible, ATTENTION_LERP_SPEED * delta)

    var amp: Vector2 = _drift_amplitude() * attention
    var offset: Vector2 = _drift_offset()

    # Respiration : horloge non déformée, indépendante de l'attention.
    var breath: float = sin(TAU * warp_clock / BREATH_PERIOD) * BREATH_AMPLITUDE

    face_root.position = Vector3(
        amp.x * offset.x,
        amp.y * offset.y + breath,
        noise_macro_x.get_noise_1d(drift_time + 500.0) * 0.6
    )
    face_root.rotation = Vector3(
        noise_micro_y.get_noise_1d(drift_time + 900.0) * 0.07 * attention,
        noise_macro_y.get_noise_1d(drift_time + 300.0) * 0.12 * attention,
        noise_micro_x.get_noise_1d(drift_time + 700.0) * 0.05 * attention
    )


func _handle_eye_tracking():
    var viewport = get_viewport()
    if viewport:
        var mouse_pos = viewport.get_mouse_position()
        var viewport_size = viewport.get_visible_rect().size
        var normalized = (mouse_pos - viewport_size / 2.0) / (viewport_size / 2.0)
        if face_root.has_method("set_eye_look"):
            face_root.set_eye_look(normalized)
