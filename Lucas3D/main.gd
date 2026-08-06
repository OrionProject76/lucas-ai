extends Node3D

@onready var face_root: Node3D = $FaceRoot

func _ready():
    _setup_noise()
    print("Lucas3D Desktop Pal demarre")
    # ⚠️ _force_fullscreen() RETIRE DE L'APPEL le 06/08/2026.
    #
    # C'etait une SECONDE configuration de fenetre, concurrente de
    # WindowManager.setup_window() appele juste apres — elle forcait
    # plein ecran ET always_on_top, puis setup_window() repassait
    # derriere. Deux sources de verite pour le meme reglage, dont une
    # qui remettait exactement le flag a l'origine de l'incident du
    # Gestionnaire des taches. WindowManager est desormais seul a
    # configurer la fenetre.
    WindowManager.setup_window()
    _masquer_hud()
    Global.main_ready.emit()


func _masquer_hud():
    # ⚠️ ETAPE 1 (06/08/2026) — perimetre valide par Cyril : la petite
    # fenetre en coin, RIEN D'AUTRE. Le HUD complet (TopBar, LeftPanel,
    # RightPanel, BackgroundGrid) restait instancie et se contentait de
    # retrecir dans les 600x600 : c'est l'interface plein ecran vue par
    # Cyril, comprimee — pas un perimetre respecte.
    #
    # Masque plutot que supprime de la scene : reversible en une ligne
    # quand le HUD reviendra a son propre chantier.
    var hud := get_node_or_null("HUD")
    if hud:
        hud.visible = false
        print("HUD masque (perimetre etape 1)")
    else:
        print("HUD introuvable — rien a masquer")

# ⚠️ PLUS APPELEE depuis le 06/08/2026 — voir _ready(). Conservee, non
# supprimee : elle documente la configuration plein ecran d'origine, et
# la supprimer masquerait ce qui a reellement tourne jusqu'ici.
# NE PAS LA RAPPELER sans relire l'incident du Gestionnaire des taches
# (window_manager.gd, bloc ALWAYS_ON_TOP RETIRE).
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
# ⚠️ 1.7 saturait le clamp : X atteignait EXACTEMENT +-5.79 sur 20 min,
# donc l'avatar COLLAIT aux bords au lieu d'en repartir — des temps morts
# plats, l'inverse d'organique. A 1.15 la valeur brute sature rarement.
const MACRO_GAIN := 1.30
const MICRO_GAIN := 0.22

# Déformation du temps. À 0.08 l'avatar s'immobilise presque — une vraie
# pause ; à 1.9 il file. Comme la déformation porte sur l'horloge
# PARTAGÉE, la pause est cohérente sur les deux axes : il s'arrête
# entièrement, ce qui se lit comme de l'attention. Une pause sur un seul
# axe se lirait comme un bug.
# ⚠️ Plage resserree : 0.08-1.9 donnait un rapport de 24 sur l'horloge,
# d'ou des a-coups brusques. L'impression d'organique vient bien plus du
# changement de DIRECTION que de l'ecart de vitesse brut.
const SPEED_MIN := 0.25
const SPEED_MAX := 1.35

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

# Inclinaison induite par la vitesse. Faible : au-dela, elle se remarque
# comme un effet plutot que comme un mouvement.
# ⚠️ 0.035 etait IMPERCEPTIBLE, mesure a l'appui : mediane 0.76 deg,
# p90 1.72 deg — sous le degre la moitie du temps, et noye par la rotation
# ambiante du bruit qui fait deja 1.71 deg de mediane. A 0.09 : p90 ~4.4
# deg, max ~11 deg, soit une inclinaison qui se lit sans se remarquer
# comme un effet.
const LEAN_GAIN := 0.09
var lean: Vector2 = Vector2.ZERO

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


# ⚠️ Le bruit fractal est quasi-gaussien : il se concentre autour de zero.
# Mesure sur 20 minutes, repartition verticale en 4 bandes : 8/39/39/14 —
# l'avatar passait 78 % du temps dans la moitie centrale. Il POUVAIT aller
# partout, il n'y ALLAIT presque jamais. Cette courbe etale la cloche vers
# les bords sans deplacer sa moyenne.
const SPREAD_EXPONENT := 0.85

# ⚠️ tanh(1.0) ne vaut que 0.76 : une limitation brute RETRECIT la course.
# Premiere tentative, mesuree : X ne parcourait plus que +-4.1 au lieu de
# +-5.79. On normalise pour qu'une entree de 1.0 ressorte a 1.0 exactement.
const LIMIT_K := 1.6


func _etaler(v: float) -> float:
    """Pousse les valeurs moyennes vers les extremes, signe conserve."""
    return sign(v) * pow(abs(v), SPREAD_EXPONENT)


func _limiter(v: float) -> float:
    """
    Limitation DOUCE au lieu d'un clamp dur.

    Un clamp aplatit : arrive au bord, la position ne bouge plus du tout.
    tanh comprime progressivement — approcher le bord ralentit, ce qui se
    lit comme une decision de faire demi-tour plutot que comme un mur.
    """
    return tanh(v * LIMIT_K) / tanh(LIMIT_K)


func _drift_offset() -> Vector2:
    """Position normalisée dans [-1, 1], macro + micro."""
    var bx: float = noise_macro_x.get_noise_1d(drift_time) * MACRO_GAIN         + noise_micro_x.get_noise_1d(drift_time) * MICRO_GAIN
    var by: float = noise_macro_y.get_noise_1d(drift_time) * MACRO_GAIN         + noise_micro_y.get_noise_1d(drift_time) * MICRO_GAIN
    return Vector2(_limiter(_etaler(bx)), _limiter(_etaler(by)))


func _handle_face_float(delta: float):
    warp_clock += delta
    drift_time += delta * _drift_speed()

    var cible: float = 1.0 if Global.lucas_state == "idle" else ATTENTION_DRIFT_SCALE
    attention = move_toward(attention, cible, ATTENTION_LERP_SPEED * delta)

    var amp: Vector2 = _drift_amplitude() * attention
    var offset: Vector2 = _drift_offset()

    # Respiration : horloge non déformée, indépendante de l'attention.
    var breath: float = sin(TAU * warp_clock / BREATH_PERIOD) * BREATH_AMPLITUDE

    var nouvelle := Vector3(
        amp.x * offset.x,
        amp.y * offset.y + breath,
        noise_macro_x.get_noise_1d(drift_time + 500.0) * 0.6
    )

    # ⚠️ LE CHAINON PERCEPTIF QUI MANQUAIT. Les chiffres de trajectoire
    # etaient bons (rapport de vitesse 70x, pauses, changements de
    # direction) et pourtant le rendu restait mecanique : parce que
    # c'etait une TRANSLATION RIGIDE. Une bille qui glisse. Un etre
    # vivant s'incline dans ses changements de direction — il anticipe.
    # On derive la vitesse et on penche proportionnellement. Aucun
    # chiffre de trajectoire ne change ; seule la lecture change.
    if delta > 0.0:
        var v := (nouvelle - face_root.position) / delta
        lean = lean.lerp(Vector2(v.x, v.y).limit_length(6.0) * LEAN_GAIN, delta * 3.0)

    face_root.position = nouvelle
    face_root.rotation = Vector3(
        noise_micro_y.get_noise_1d(drift_time + 900.0) * 0.07 * attention - lean.y,
        noise_macro_y.get_noise_1d(drift_time + 300.0) * 0.12 * attention + lean.x,
        noise_micro_x.get_noise_1d(drift_time + 700.0) * 0.05 * attention - lean.x * 0.6
    )


func _handle_eye_tracking():
    var viewport = get_viewport()
    if viewport:
        var mouse_pos = viewport.get_mouse_position()
        var viewport_size = viewport.get_visible_rect().size
        var normalized = (mouse_pos - viewport_size / 2.0) / (viewport_size / 2.0)

        # ⚠️ AXE Y INVERSE — corrige le 07/08/2026, signale par Cyril :
        # les yeux regardaient EN BAS quand la souris montait.
        #
        # Deux conventions opposees se rencontraient ici sans conversion :
        #   - coordonnees ECRAN (get_mouse_position) : Y vers le BAS
        #   - coordonnees 3D (eye_base_left.y + decalage.y dans
        #     face_controller.gd, l.142) : Y vers le HAUT
        #
        # Souris qui monte -> mouse_pos.y diminue -> normalized.y negatif
        # -> decalage.y negatif -> l'oeil DESCEND. Exactement l'inverse.
        #
        # La conversion se fait ICI, au point de passage ecran -> 3D, et
        # pas dans set_eye_look() : c'est le seul endroit du code ou une
        # coordonnee ecran existe. set_eye_look() est un point d'entree en
        # convention 3D, comme les saccades — y cacher une inversion le
        # rendrait faux pour tout autre appelant.
        #
        # (Ce ne serait PAS visible sur les saccades, qui tirent dans
        # randf_range(-0.6, 0.6), symetrique autour de zero. La raison est
        # la coherence du contrat, pas un bug qu'on eviterait.)
        normalized.y = -normalized.y

        if face_root.has_method("set_eye_look"):
            face_root.set_eye_look(normalized)
