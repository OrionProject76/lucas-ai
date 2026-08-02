# scripts/_expr.gd — planche de controle des expressions
#
# OUTIL DE MESURE, pas du code de production : ce noeud n'est PAS dans
# main.tscn. Pour s'en servir, l'y ajouter comme enfant de Main :
#
#   [ext_resource type="Script" path="res://scripts/_expr.gd" id="9_x"]
#   [node name="Expr" type="Node" parent="."]
#   script = ExtResource("9_x")
#
# Il fige la derive, force tour a tour les quatre etats, laisse la pose
# converger et ecrit user://expr_<etat>.png. C'est ainsi qu'ont ete
# trouvees la bouche invisible et l'asymetrie des yeux.
#
# ⚠️ Le double await en tete est necessaire : le _ready() d'un enfant
# s'execute AVANT celui du parent, donc main.face_root est encore nul.
extends Node
func _ready():
    await get_tree().process_frame
    await get_tree().process_frame
    var etats := ["idle", "thinking", "speaking", "watching"]
    var m = get_parent()
    # Immobiliser la derive : on veut comparer les visages, pas les positions.
    m.set_process(false)
    m.face_root.position = Vector3.ZERO
    m.face_root.rotation = Vector3.ZERO
    for e in etats:
        Global.lucas_state = e
        # Laisser la pose converger (POSE_LERP 2.5 -> ~1.6 s pour 98 %)
        await get_tree().create_timer(2.5).timeout
        var img := get_viewport().get_texture().get_image()
        img.save_png("user://expr_%s.png" % e)
        print("EXPR CAPTURE ", e)
    get_tree().quit()
