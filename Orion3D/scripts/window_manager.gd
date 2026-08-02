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
# Etat de depart, MESURE via WindowFromPoint sur huit points : Godot
# recevait les clics PARTOUT, barre des taches Windows comprise. Deux
# causes — setup_window() appelait _set_click_through(false), et un
# tableau vide DESACTIVE le passthrough ; et le mode « actif » posait un
# cercle de 200 px au CENTRE de l'ecran, alors que l'avatar derive et que
# les panneaux sont sur les bords.
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


# ⚠️ NE PLUS UTILISER window_set_mouse_passthrough(polygone) SUR WINDOWS.
# Il y est implemente par une REGION DE FENETRE, qui ne decoupe pas
# seulement les clics mais aussi LE RENDU : le trou central rendait
# l'avatar et tout le centre du HUD invisibles. Verifie a la capture —
# seuls les bords du HUD subsistaient, le bureau apparaissait au milieu.
#
# WINDOW_FLAG_MOUSE_PASSTHROUGH pose WS_EX_TRANSPARENT : les clics
# traversent TOUTE la fenetre, sans toucher au rendu. Il est global, donc
# on le bascule selon la position du curseur — sur le HUD il s'eteint
# (la fenetre recoit), ailleurs il s'allume (ca traverse).
#
# mouse_get_position() rend la position GLOBALE du curseur meme sans
# focus : le sondage fonctionne alors que la fenetre est en NO_FOCUS.

# ⚠️⚠️ LIMITE DE PLATEFORME, MESUREE — NE PAS REESSAYER SANS LIRE CECI.
#
# Sur Windows, avec Godot 4.7, AUCUNE des deux voies ne donne a la fois un
# rendu complet et des clics qui traversent :
#
#   • window_set_mouse_passthrough(polygone) DECOUPE LE RENDU. Preuve :
#     avec un trou rectangulaire de (1200,500) a (2600,1600), la tete de
#     l'avatar apparait TRANCHEE VERTICALEMENT a x = 1200 exactement.
#     Le centre de l'overlay cesse simplement d'etre dessine.
#
#   • WINDOW_FLAG_MOUSE_PASSTHROUGH est SANS EFFET. La bascule s'execute
#     bien (verifie par journalisation : true -> false sur le HUD ->
#     true au centre), mais GWL_EXSTYLE reste identique aux deux
#     positions et WS_EX_TRANSPARENT n'est jamais pose.
#
# L'etat actuel privilegie le RENDU : l'avatar et le HUD s'affichent
# entierement, mais la fenetre capte les clics. Le vrai correctif demande
# de poser WS_EX_TRANSPARENT par du code natif (GDExtension), hors de
# portee de GDScript. En attente d'arbitrage de Cyril.
var _traverse: bool = false


func _dans_hud(p: Vector2i) -> bool:
    """Le curseur est-il sur une zone interactive de Luca's ?"""
    var w := screen_size.x
    var h := screen_size.y
    var bas := h - int(TASKBAR_RESERVED)
    # La barre des taches Windows n'appartient jamais a Luca's.
    if p.y >= bas:
        return false
    if p.y < int(HUD_TOP):
        return true
    if p.y >= bas - int(HUD_BOTTOM):
        return true
    if p.x < int(HUD_LEFT):
        return true
    if p.x >= w - int(HUD_RIGHT):
        return true
    return false


func _appliquer_traverse(valeur: bool):
    """
    ⚠️ SANS EFFET AUJOURD'HUI — et c'est volontaire de le laisser en place.

    L'appel ci-dessous ne fait rien sur Windows (voir l'encadre plus
    haut). Ce qui est conserve, c'est la POLITIQUE : _dans_hud() decrit
    exactement quelles zones doivent intercepter, et cette politique est
    verifiee. Le jour ou WS_EX_TRANSPARENT sera pose par une GDExtension,
    seul le corps de cette fonction changera.

    Ne pas supprimer en croyant nettoyer du code mort : ce serait perdre
    la partie qui a demande le plus de mesures.
    """
    if valeur == _traverse:
        return
    _traverse = valeur
    DisplayServer.window_set_flag(
        DisplayServer.WINDOW_FLAG_MOUSE_PASSTHROUGH, valeur, window.get_window_id()
    )


func _process(_delta: float):
    if not Global.click_through or not window:
        return
    _appliquer_traverse(not _dans_hud(DisplayServer.mouse_get_position()))


func _set_click_through(enabled: bool):
    Global.click_through = enabled
    if not enabled:
        _appliquer_traverse(false)


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
