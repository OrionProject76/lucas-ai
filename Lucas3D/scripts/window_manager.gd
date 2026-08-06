extends Node

var window: Window
var screen_size: Vector2i
var _scale: float = 1.0

func _ready():
    window = get_window()
    screen_size = DisplayServer.screen_get_size()
    # hud_canvas.tscn est dessine dans le canevas de conception (project.godot :
    # viewport_width=1920), mis a l'echelle par stretch/mode=canvas_items sur la
    # taille reelle de la fenetre. Sans ce facteur, les seuils HUD_* ci-dessous
    # sont compares a des coordonnees de souris en pixels reels : sur cette
    # machine (3840x2160, facteur 2), toute la bande interactive du bas se
    # retrouvait au-dessus de la barre de saisie reelle au lieu de la couvrir.
    _scale = screen_size.x / DESIGN_WIDTH

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
    _appliquer_passthrough_total()
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

# Bords du HUD, en pixels du canevas de CONCEPTION (1920x1080) — voir
# _scale plus haut pour la conversion vers les pixels reels de l'ecran.
# Suivent hud_canvas.tscn exactement : LeftPanel large de 320, RightPanel
# de 400, TopBar haute de 60, BottomBar de 70.
const DESIGN_WIDTH := 1920.0
const HUD_LEFT := 320.0
const HUD_RIGHT := 400.0
const HUD_TOP := 60.0
const HUD_BOTTOM := 70.0

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
# ⚠️ PERIME — ce paragraphe decrit l'etat d'AVANT l'incident du 02/08.
# « L'etat actuel privilegie le RENDU : l'avatar et le HUD s'affichent
# entierement, mais la fenetre capte les clics. » Ce n'est plus vrai
# depuis que _appliquer_passthrough_total() est le defaut : aujourd'hui
# c'est l'inverse exact — tout traverse, rien ne s'affiche. Voir le bloc
# « CORRIGE LE 06/08/2026 » plus bas, qui fait foi.
#
# Reste vrai : le seul correctif est de poser WS_EX_TRANSPARENT par du
# code natif (GDExtension), hors de portee de GDScript. Arbitre par
# Cyril le 06/08/2026 : reporte, catalogue dans IDEAS.md, et fenetre en
# coin en attendant.
#
# ⚠️⚠️ INCIDENT DU 02/08/2026 — le bureau ENTIER se bloquait, pas
# seulement le HUD. La ligne juste au-dessus etait fausse : la fenetre ne
# "captait les clics" pas seulement sur elle-meme, elle les captait sur
# TOUT l'ecran, en permanence, quelle que soit la valeur du flag —
# puisque WINDOW_FLAG_MOUSE_PASSTHROUGH est SANS EFFET MESURE (voir plus
# haut). _dans_hud() et son appel par _process() ne changeaient donc rien
# en pratique : le vrai defaut a toujours ete "tout capte", jamais "tout
# traverse" comme le code semblait le dire.
#
# Regle non negociable de Cyril, posee apres ce blocage : le comportement
# PAR DEFAUT doit garantir que le bureau n'est jamais bloque, quitte a
# n'avoir ENCORE aucune zone cliquable. window_set_mouse_passthrough(region)
# est le seul mecanisme MESURE qui fasse reellement passer les clics sur
# cette machine.
#
# ⚠️⚠️ CORRIGE LE 06/08/2026 — ces quatre lignes affirmaient le
# contraire de la realite, et c'est mesure maintenant.
#
# Elles disaient : « son defaut connu (decouper le rendu) n'apparaissait
# qu'a la FRONTIERE d'une region PARTIELLE a l'interieur de la fenetre
# visible : une region totalement hors ecran n'a pas de frontiere interne
# visible, donc pas de raison de couper le rendu. » C'etait un PARI, ecrit
# le 02/08 sans etre verifie.
#
# Le pari est FAUX. Etape 0 de la session Godot supervisee, binaire
# exporte lance sous les yeux de Cyril : bureau parfaitement reactif
# (le passthrough marche), et AUCUN pixel a l'ecran — ni visage, ni HUD,
# rien. Process vivant, fenetre 3840x2160 existante, scene complete,
# zero erreur de script.
#
# La region ne dit pas seulement OU les clics passent : elle dit aussi CE
# QUI EST RENDU. Region entierement hors ecran => surface de rendu nulle
# => fenetre totalement invisible. Ce n'est pas un effet de bord au
# niveau des frontieres, c'est la regle.
#
# Recoupe la mesure du 02/08 dans l'autre sens : avec un trou PARTIEL a
# x=1200, la tete apparaissait tranchee exactement a x=1200. Meme
# mecanisme, deux observations independantes.
#
# Consequence : en GDScript pur sur Godot 4.7 + Windows, c'est BINAIRE —
# soit tout s'affiche et tout est capte (le bureau se bloque, incident du
# 02/08), soit tout traverse et rien ne s'affiche (l'etat actuel). Aucune
# troisieme voie sans la GDExtension (IDEAS.md).
#
# ➜ D'ou l'arbitrage de Cyril du 06/08 : fenetre EN COIN (~600x600, en
#   bas a droite, au-dessus de la barre des taches) plutot que plein
#   ecran. Une petite fenetre peut rendre normalement et ne capter les
#   clics que sur elle-meme — vivable, la ou 3840x2160 ne l'etait pas.
#   A implementer en etape 1, pas encore fait ici.
#
# _dans_hud() reste ci-dessous, INUTILISEE pour l'instant : elle decrit la
# politique des zones cliquables du HUD, a reconnecter plus tard a une
# region reelle (pas au flag mort) une fois validee sans risque de blocage.
const HORS_ECRAN := Vector2(-10.0, -10.0)


func _region_totalement_hors_ecran() -> PackedVector2Array:
    # Polygone degenere (aire nulle) mais volontairement NON VIDE : un
    # tableau [] desactive le passthrough (capture totale — l'inverse de
    # l'effet recherche). Trois points identiques hors fenetre donnent un
    # passthrough actif sur toute la fenetre, sans jamais definir de zone
    # interactive.
    #
    # ⚠️ ET AUSSI, mesure le 06/08/2026 : cette region rend la fenetre
    # ENTIEREMENT INVISIBLE. La region gouverne le rendu autant que les
    # clics (voir le bloc corrige plus haut). Ce n'est donc pas « le HUD
    # attend d'etre reconnecte » : rien ne s'affiche du tout, par
    # construction. C'est ce qui rend cet etat SUR.
    return PackedVector2Array([HORS_ECRAN, HORS_ECRAN, HORS_ECRAN])


func _region_fenetre_entiere() -> PackedVector2Array:
    var w := float(screen_size.x)
    var h := float(screen_size.y)
    return PackedVector2Array([
        Vector2(0, 0), Vector2(w, 0), Vector2(w, h), Vector2(0, h)
    ])


func _appliquer_passthrough_total():
    """Etat SUR par defaut au demarrage : rien n'est interactif, tout traverse.

    ⚠️ Et rien ne s'AFFICHE non plus — mesure le 06/08/2026, etape 0.
    La securite de cet etat vient precisement de la : une fenetre qui ne
    rend aucun pixel ne peut pas bloquer le bureau. Ne pas l'appeler en
    croyant qu'il laissera l'avatar visible.
    """
    DisplayServer.window_set_mouse_passthrough(_region_totalement_hors_ecran(), window.get_window_id())
    Global.click_through = true


func _appliquer_capture_totale():
    """Bascule manuelle (F12) : toute la fenetre redevient interactive."""
    DisplayServer.window_set_mouse_passthrough(_region_fenetre_entiere(), window.get_window_id())
    Global.click_through = false


func _dans_hud(p: Vector2i) -> bool:
    """Le curseur est-il sur une zone interactive de Luca's ?"""
    var w := screen_size.x
    var h := screen_size.y
    var bas := h - int(TASKBAR_RESERVED)
    # La barre des taches Windows n'appartient jamais a Luca's.
    if p.y >= bas:
        return false
    if p.y < int(HUD_TOP * _scale):
        return true
    if p.y >= bas - int(HUD_BOTTOM * _scale):
        return true
    if p.x < int(HUD_LEFT * _scale):
        return true
    if p.x >= w - int(HUD_RIGHT * _scale):
        return true
    return false


func toggle_click_through():
    if Global.click_through:
        _appliquer_capture_totale()
    else:
        _appliquer_passthrough_total()
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
