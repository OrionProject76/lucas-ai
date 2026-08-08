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

## L'écran de destination — contraintes mesurées le 09/08/2026

Relevé sur la machine, pas supposé :

| | |
|---|---|
| Dalle | LG **OLED**, 3840 × 2160, 120 Hz, VRR 40–120 Hz |
| Couleur | HDR Dolby Vision, 10 bits/canal, gamut P3, 1387 nits en pic |
| Mise à l'échelle Windows | **300 %** → il ne reste que **1280 × 720 points logiques** |

### Ce que le 300 % implique

C'est la contrainte dominante, bien avant la 4K. La surface de composition
disponible est celle d'un petit écran : après la barre de titre, il reste
environ 600 points de hauteur. C'est ce qui provoquait le chevauchement des
panneaux — un manque de place réel, pas seulement un défaut de calcul.

À noter, pour éviter un contresens : passer Godot en « 4K natif » **n'apporte
aucune place supplémentaire**. Windows dessine déjà en pixels physiques réels
(`devicePixelRatio = 3`), la netteté est acquise. Le scaling ne fixe que la
*taille apparente*. Le seul vrai réglage est donc `ui_scale`, à trouver à la
distance de vision réelle — c'est à ça que sert le curseur **Lisibilité** de
l'aperçu, dont la valeur se recopie ensuite dans le thème.

### Ce que l'OLED impose

Une interface fixe affichée des heures **marque la dalle de façon
permanente**. Ce n'est pas un risque théorique pour un bureau permanent.
Le bloc `oled` de `themes.json` porte les trois règles, et elles valent
autant pour Godot que pour l'aperçu :

- **Pixel shift** — toute la scène se décale de 4 px logiques (12 physiques)
  toutes les 90 s, en cycle de 4 positions. Invisible à l'œil, suffisant pour
  qu'aucun bord de panneau ne stationne sur un pixel. *Déjà actif dans
  l'aperçu.*
- **Jamais de blanc pur en aplat statique** — un fond clair plein écran, c'est
  la dalle à pleine puissance en continu. Le thème **Atelier** porte pour cette
  raison un avertissement affiché dans l'inspecteur : il reste utilisable, mais
  par sessions courtes.
- **Éviter les zones lumineuses immobiles** — barres de titre pleines, bordures
  vives, halos fixes marquent en premier. Préférer l'accent sur du texte et des
  traits fins plutôt que sur des aplats.

En HDR, enfin, un accent saturé sort **beaucoup** plus lumineux que sur un
écran classique : le cyan du thème Holographique est à surveiller en usage
nocturne.

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

### Les décisions qui restent

1. **Régler `ui_scale`** — le seul test qui ne peut pas se faire au clavier :
   lancer l'aperçu, s'installer à la distance habituelle, bouger le curseur
   *Lisibilité* jusqu'à lire sans effort, reporter la valeur dans le thème.

2. **L'ancrage**, avant la moindre ligne de GDScript : overlay plein écran
   permanent, ou mode dédié activé à la demande ? Ce n'est pas un détail de
   confort — un overlay Godot plein écran toujours au premier plan capture les
   clics sur tout le bureau (incident du 02/08/2026, `ROADMAP.md` §3, section
   Godot). Et sur OLED, « permanent » a un coût que « à la demande » n'a pas.

3. **Godot à 120 fps** — le moteur plafonne à 60 par défaut ; l'écran fait 120
   avec VRR. À régler au moment de la mise en place de la scène.
