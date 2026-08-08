# ProjetWindows3D — bureau 3D Luca's

Option **A** retenue le 09/08/2026 : un environnement 3D plein écran en Godot 4,
posé par-dessus Windows. Windows continue de tourner derrière ; on ne le regarde
plus. Aucune modification du DWM, aucun P/Invoke Win32.

Le comparatif qui a mené à ce choix reste consultable dans
`maquette_options.html` (options A / B / C côte à côte).

---

## Voir l'aperçu

Double-clic sur **`apercu.bat`**. Il démarre un serveur local sur
`127.0.0.1:8777` — ce PC uniquement, rien n'est exposé sur le réseau — et ouvre
la page. Ferme la fenêtre noire pour arrêter le serveur.

Ouvrir `bureau3d.html` directement par double-clic **ne marche pas** : une page
en `file://` n'a pas le droit de lire `themes.json` à côté d'elle. La page le dit
et rappelle la marche à suivre si ça arrive.

---

## Changer l'apparence

Tout se joue dans **`themes.json`**, et nulle part ailleurs. C'est la source de
vérité unique : ni `bureau3d.html` ni le futur code Godot ne contiennent de
couleur ou de dimension en dur.

Modifier une valeur → enregistrer → **F5** sur la page. C'est tout.

### Les trois thèmes livrés

| Thème | Pour quoi | Signature |
|---|---|---|
| **Studio** *(par défaut)* | Travail quotidien, sombre | Ardoise, accent bleu acier, angles nets, aucun halo, panneaux immobiles |
| **Atelier** | Travail de jour, volets ouverts | Même sobriété, en clair |
| **Holographique** | La version démonstration | Verre teinté, néon cyan, profondeur maximale, flottement, grille de sol |

`"default"` en haut du fichier décide de celui qui s'affiche à l'ouverture.

### Ajouter un thème

Copier un bloc existant dans `"themes"`, lui donner une nouvelle clé, ajuster.
**Le bouton apparaît tout seul** en haut à droite au prochain rechargement —
rien à déclarer ailleurs.

### Les leviers qui changent vraiment quelque chose

En s'en tenant à quatre valeurs, on couvre l'essentiel de l'écart entre
« sobre » et « spectaculaire » :

- `space.depth_scale` — l'éloignement des panneaux. Le levier le plus visible.
  `1.0` = immersif, `0.5` = sobre, `0` = tableau de bord plat.
- `panel.glow_strength` — `0` supprime tout effet néon d'un coup.
- `space.float_amplitude_px` — `0` fige les panneaux. Un panneau qui respire
  est joli cinq minutes, fatigant sur huit heures.
- `panel.blur_px` avec l'alpha de `colors.panel_fill` — décide si on voit à
  travers les panneaux ou non.

Chaque token est décrit en clair dans le bloc `_tokens` du fichier lui-même.

---

## Le contrat avec Godot

`themes.json` est délibérément du JSON neutre, sans rien de propre au web, pour
qu'un seul fichier serve les deux mondes :

```gdscript
var txt := FileAccess.get_file_as_string("res://themes.json")
var data: Dictionary = JSON.parse_string(txt)
var theme: Dictionary = data["themes"][data["default"]]
```

Les mêmes clés alimenteront les `StandardMaterial3D`, l'écartement des panneaux
et l'intensité du `WorldEnvironment`. **Aucune valeur ne doit être recopiée dans
une scène `.tscn`** : le jour où une couleur vit à deux endroits, les deux
divergent — c'est exactement ce que ce fichier existe pour empêcher.

> ⚠️ Ce chargeur Godot **n'est pas encore écrit**. L'extrait ci-dessus décrit
> l'engagement pris, pas du code existant. `Lucas3D/` n'a pas été touché.

---

## État au 09/08/2026

| | |
|---|---|
| Décision | Option A validée par Cyril |
| Livré | `themes.json`, `bureau3d.html`, `apercu.bat`, ce README |
| Vérifié | Les 3 thèmes se chargent et s'appliquent réellement dans le navigateur |
| Pas encore fait | Tout Godot. Aucun fichier de `Lucas3D/` modifié |

### La prochaine décision à prendre

**L'ancrage**, avant d'écrire la moindre ligne de GDScript : overlay plein écran
permanent, ou mode dédié qu'on active à la demande ?

Ce n'est pas un détail de confort. Un overlay Godot plein écran toujours au
premier plan capture les clics sur tout le bureau — l'incident du 02/08/2026
(`ROADMAP.md` §3, section Godot). Le problème se conçoit avant, pas après.
