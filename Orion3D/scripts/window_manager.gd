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
    _set_click_through(true)
    print("Fenetre configuree : " + str(screen_size))

# ── Zones cliquables ──────────────────────────────────────────────────
#
# ⚠️ SEMANTIQUE DE window_set_mouse_passthrough : le polygone definit ce
# qui REÇOIT les clics ; tout le reste TRAVERSE. Un tableau vide DESACTIVE
# le passthrough, donc la fenetre intercepte TOUT.
#
# L'ancien code appelait _set_click_through(false) au demarrage, donc
# tableau vide, donc interception totale. Mesure au demarrage, via
# WindowFromPoint sur huit points : Godot recevait les clics PARTOUT, y
# compris sur la barre des taches Windows. Et le mode « actif » posait un
# cercle de 200 px au CENTRE de l'ecran — alors que l'avatar derive et que
# les panneaux HUD sont sur les bords : la seule zone cliquable etait
# celle ou il n'y a rien.
#
# La zone qui intercepte est desormais le CADRE du HUD, trace en un seul
# polygone « en beignet » : contour exterieur, puis contour interieur
# parcouru en sens inverse. Le centre — ou vit l'avatar — traverse.
#
# Decision de Cyril, 02/08/2026 : l'avatar TRAVERSE tant qu'aucune action
# ne lui est associee. Une forme qui derive et bloque des clics au hasard
# de sa trajectoire serait vite insupportable ; on peut toujours parler a
# Luca's par la barre de saisie, qui reste cliquable.

# Bords du HUD, en pixels. Suivent hud_canvas.tscn : LeftPanel et
# RightPanel font 320 de large, la barre du haut 70, celle du bas 80.
const HUD_LEFT := 320.0
const HUD_RIGHT := 320.0
const HUD_TOP := 70.0
const HUD_BOTTOM := 80.0

# ⚠️ Hauteur reservee a la barre des taches Windows. MESUREE sur cette
# machine : y 2016 a 2160, soit 144 px.
# DisplayServer.screen_get_usable_rect() ne convient PAS ici : elle rend
# l'ecran entier (0,0,3840,2160), barre des taches comprise — verifie en
# l'affichant. Le cadre cliquable retombait donc dessus et Godot captait
# les clics sur la barre des taches.
# A revoir si Cyril change l'echelle d'affichage ou deplace sa barre.
const TASKBAR_RESERVED := 144.0


func _region_hud() -> PackedVector2Array:
    """
    Le cadre du HUD, en un seul polygone troue.

    Deux bornes, et les deux ont ete trouvees par la mesure :

    ⚠️ Le contour EXTERIEUR s'arrete a `bas_utile`, pas au bas de l'ecran.
    Tout ce qui est en dessous — la barre des taches — sort du polygone et
    traverse donc. Premiere version : le contour descendait jusqu'a `h`,
    si bien que la bande de la barre des taches faisait partie du cadre
    cliquable, et WindowFromPoint confirmait que Godot y captait les clics.

    ⚠️ Le TROU central couvre tout l'interieur : c'est la que vit
    l'avatar, et il doit traverser (decision de Cyril, 02/08/2026).
    """
    var w := float(screen_size.x)
    var h := float(screen_size.y)
    var bas_utile := h - TASKBAR_RESERVED
    var l := HUD_LEFT
    var r := w - HUD_RIGHT
    var t := HUD_TOP
    var b := bas_utile - HUD_BOTTOM
    return PackedVector2Array([
        # contour exterieur, borne au-dessus de la barre des taches
        Vector2(0, 0), Vector2(w, 0), Vector2(w, bas_utile), Vector2(0, bas_utile), Vector2(0, 0),
        # trou central, parcouru en sens inverse
        Vector2(l, t), Vector2(l, b), Vector2(r, b), Vector2(r, t), Vector2(l, t),
    ])


func _set_click_through(enabled: bool):
    Global.click_through = enabled
    var win_id = window.get_window_id()
    if enabled:
        DisplayServer.window_set_mouse_passthrough(_region_hud(), win_id)
    else:
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
