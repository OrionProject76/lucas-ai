# Référence visuelle de l'avatar — base de départ pour la Phase 1 (Assets)

**Créé le 07/08/2026**, à la demande de Cyril, pour que la prochaine session
sur l'esthétique de l'avatar reparte d'une base rassemblée plutôt que de rien.

**Statut : documentation uniquement. Aucun code Godot écrit.**

Cyril place l'interface visuelle en **deuxième priorité du projet**, après le
cerveau et le corps (Decision Engine, mémoire, sécurité).

> ⚠️ Ce document est une **référence**, pas une décision de construction. Rien
> ici n'autorise à ouvrir un chantier. Le module Avatar reste soumis à la règle
> posée le 02/08/2026 : **rien de visuel ne se construit sans Cyril devant
> l'écran** (`ROADMAP.md` §3).

---

## 0. ⚠️ Trois corrections d'entrée, et deux éléments que je n'ai pas

Ce document est destiné à servir de source fiable. Les erreurs de renvoi y
seraient donc plus coûteuses qu'ailleurs — voici ce qui a été vérifié et
redressé avant écriture.

### Corrigé — « Mode Shell » n'existe pas dans `VISION_LONG_TERME.md`

L'instruction renvoyait à un « Mode Shell déjà acté (§VISION_LONG_TERME.md) ».
**Ce paragraphe n'existe pas.** Dans ce projet, « mode shell » désigne tout
autre chose : `modules/automation_manager.py`, constante `SHELL_LIKE_APPS`,
**retirée de la liste blanche** — un sujet de **sécurité** (exécution de
commandes), sans aucun rapport avec l'interface (`IDEAS.md` l. 921).

**Mais le fond de l'idée est bien documenté**, sous un autre nom :
`VISION_LONG_TERME.md` §2 (l. 69-86) décrit déjà un « environnement
holographique 3D », l'analogie JARVIS assumée mot pour mot, la « tête
holographique 3D comme centre de gravité de l'interface », et des « fichiers,
applications, données encapsulés en panneaux holographiques ».

➜ **C'est ce §2 qu'il faut citer**, pas un « Mode Shell ».

### Corrigé — l'incident de la fenêtre plein écran est en §5.67

L'instruction renvoyait à `§5.66`. Celle-ci traite de la revalidation générale
d'avant-Godot. L'incident (fenêtre par-dessus le Gestionnaire des tâches,
`always_on_top` retiré) est en **§5.67**.

### Corrigé — le choix STT date du 01/08, pas du 03/08

`faster-whisper` a été choisi **le 01/08/2026**, et pour une raison qui compte
ici : **tourner en CPU afin de ne pas se disputer la VRAM avec Ollama**
(`ROADMAP.md` l. 467-474, `VISION_LONG_TERME.md` §3).

### ⛔ Deux éléments cités que je n'ai jamais reçus

Dits franchement, parce qu'un document de référence ne doit pas affirmer
l'existence d'artefacts que personne ne peut retrouver :

| Élément cité | Réalité |
|---|---|
| **Code Three.js « fourni par Cyril »** | **Jamais transmis dans cette conversation.** Aucun code Three.js n'y figure. Le §2 ci-dessous décrit donc le *comportement* tel que Cyril l'a énoncé, sans code source à l'appui. |
| **Maquette interactive « produite dans cette conversation »** | **Jamais produite ici.** Cette conversation a porté sur Ollama, la veille modèles, ruff/mypy/couverture/mutation, la revalidation sécurité et les étapes 0-1 de Godot. Aucune maquette HTML/canvas. |

Ils viennent vraisemblablement d'un **autre outil ou d'une autre session**
(le dépôt contient déjà des documents produits ailleurs : specs Claude,
analyse comparative Kimi). **Si ces artefacts existent, il faut les
retrouver et les déposer dans `cowork_workspace/`** — sans quoi la
prochaine session repartira d'une référence qui la cite sans pouvoir la
consulter, exactement ce que ce document cherche à éviter.

---

## 1. Direction esthétique — validée par Cyril

### Les références

| Référence | Ce qui est retenu |
|---|---|
| **JARVIS** (*Iron Man*) | Des **fenêtres contextuelles spatiales** qui apparaissent à la sollicitation et **s'effacent au repos**. L'interface n'est pas permanente : elle répond. |
| **Blade Runner 2049 / Joi** | La **présence holographique** — une entité qui occupe l'espace sans corps physique. |

### Le principe central

> Visage **holographique / robotique en maillage 3D**, **pas de corps
> physique**, affiché **uniquement sur écran**, en **interface spatiale
> transparente** avec **fenêtres contextuelles à la demande**.

Cohérent avec `VISION_LONG_TERME.md` §2, qui pose déjà la tête holographique
comme centre de gravité de l'interface et les données en panneaux
holographiques.

### 🔴 Ce que la session du 06-07/08 impose à cette direction

Ces contraintes ne sont pas des préférences : elles sont **mesurées**, et elles
contredisent l'idée d'un overlay plein écran permanent.

**1. Pas de fenêtre plein écran par défaut.** L'incident du 06/08 (§5.67) : une
fenêtre plein écran `always_on_top` s'est affichée **par-dessus le Gestionnaire
des tâches**, le rendant inutilisable. `always_on_top` a été retiré, et la
fenêtre ramenée à **600×600 en coin bas-droit**.

**2. Le click-through est impossible en GDScript sur Godot 4.7 + Windows.**
Mesuré deux fois. C'est **binaire** :

| Région de passthrough | Clics | Rendu |
|---|---|---|
| absente | tout capté (le bureau se bloque) | tout s'affiche |
| hors écran | tout traverse | **rien ne s'affiche** |
| partielle | traverse hors zone | **découpé net à la frontière** |

`window_set_mouse_passthrough` est une **région de fenêtre** : elle gouverne le
rendu autant que les clics. Correctif réel = GDExtension (`IDEAS.md` #95),
**reporté**.

➜ **Conséquence directe pour l'interface spatiale** : les « fenêtres
contextuelles » de JARVIS ne peuvent pas flotter sur tout l'écran en laissant
passer les clics. Soit elles vivent dans une fenêtre bornée qui capte ses
propres clics, soit elles attendent la GDExtension. **C'est la contrainte
structurante de toute la Phase 1.**

**3. Le coût VRAM suit la taille de fenêtre.** Mesuré : **~247 Mo en 600×600**
contre **~976 Mo en 3840×2160**. Et avec `gpt-oss:20b` résident, la marge
mesurée est de **805 Mo**. Une interface plein écran mangerait cette marge.

---

## 1 bis. Cible détaillée — Desktop Pal AI (ajout du 07/08/2026)

Référence la plus proche selon Cyril. **Note d'honnêteté : la capture n'a
pas été reçue ici** — ce qui suit consigne *sa description*, pas une analyse
d'image faite depuis ce poste.

### Ce qui est validé comme cible

| Élément | Cible |
|---|---|
| **Visage** | **Humanoïde 3D translucide bleu/cyan**, lumineux, presque fantomatique — vraie structure faciale sculptée : front, pommettes, yeux lumineux, expression |
| **Yeux** | Lumineux blanc/cyan, **sans pupille marquée** — effet « entité d'énergie » |
| **Environnement** | **HUD complet type JARVIS** tout autour : jauges **circulaires** (CPU/RAM/batterie), visualiseur audio en onde, horloge large, cadrans, lignes de données, sur fond bleu nuit profond |

### L'écart réel avec l'existant, mesuré dans le code

**Le visage actuel n'est pas « schématique » par style — il l'est par
construction.** `face_root.tscn` :

```
Head      -> SphereMesh, échelle (1.0, 1.08, 0.92)
             ellipsoïde, demi-axes 2.5 / 2.7 / 2.3
EyeLeft   -> SphereMesh
EyeRight  -> SphereMesh
Mouth     -> BoxMesh
```

Trois sphères et un cube. **Il n'existe aucune géométrie faciale** — ni
front, ni pommettes, ni arête nasale, rien à sculpter ni à éclairer. Ce
n'est donc pas un réglage de shader : **il faut un mesh de tête**. C'est
l'écart principal, et il est structurel.

Côté HUD, `widget_system.gd` fournit déjà CPU/RAM/GPU — mais en
`ProgressBar` **linéaires**. Les cadrans circulaires demandés sont un
travail distinct (`draw_arc` sur un `Control`, ou un shader radial).

### ⚠️ Desktop Pal est fait avec Unreal Engine

Cyril le note lui-même, et c'est important à double titre.

**D'abord, ça n'est pas transposable tel quel** : Unreal est conçu pour ce
rendu, avec un budget mémoire et un pipeline d'éclairage sans commune
mesure.

**Ensuite, ça ne rouvre aucune question de moteur.** `CLAUDE.md` règle 2
(« Godot 4 uniquement — PAS Unity/Unreal ») et règle 10 restent entières.
Desktop Pal est une **référence esthétique**, pas une option technique. Si
quelqu'un propose un jour « prenons Unreal », la réponse est déjà écrite.

---

### 🔴 Deux conflits mesurés entre cette cible et ce que la session a établi

Ils ne disqualifient rien — ils disent **ce qu'il faudra arbitrer**. Mieux
vaut le savoir avant d'ouvrir le chantier qu'après.

#### Conflit 1 — « HUD occupant tout l'écran » rouvre l'incident du 06/08

Un HUD plein écran est une fenêtre plein écran. Or, mesuré (§5.67) :

- une fenêtre plein écran `always_on_top` est passée **par-dessus le
  Gestionnaire des tâches**, le rendant inutilisable ;
- sans `always_on_top`, un HUD plein écran **capte tous les clics du
  bureau** — puisque le click-through est impossible en GDScript.

➜ Un HUD immersif plein écran n'est **pas** un simple agrandissement de la
fenêtre actuelle. Il **exige** la GDExtension `WS_EX_TRANSPARENT`
(`IDEAS.md` #95), aujourd'hui reportée. **C'est un prérequis, pas un
détail de finition.**

#### Conflit 2 — le budget VRAM ne le permet probablement pas

Chiffres **mesurés** les 06-07/08, pas estimés :

| Configuration | VRAM |
|---|---|
| Godot 600×600, rendu actif | **~247 Mo** |
| Godot 3840×2160, **rendu NUL** (fenêtre invisible) | **~976 Mo** |
| Marge restante avec `gpt-oss:20b` résident + Godot 600×600 | **805 Mo** |

Passer en plein écran coûte au moins **+729 Mo** — et cette valeur est
**optimiste**, puisque les 976 Mo ont été mesurés avec **rien de dessiné**.
Un HUD riche (jauges, ondes, cadrans, lignes de données) coûterait
davantage.

➜ **805 − 729 ≈ 76 Mo de marge, dans le meilleur des cas.** Autrement dit :
**HUD plein écran riche + `gpt-oss:20b` résident ne tiennent
vraisemblablement pas ensemble sur 16 Go.**

Quatre sorties possibles, aucune tranchée, toutes pour Cyril :

1. **HUD borné** (fenêtre large mais pas plein écran) — conserve le modèle.
2. **Modèle plus léger** — ⚠️ relève de la règle 12 : *jamais de bascule de
   modèle en production sans validation explicite de Cyril*.
3. **Décharger le modèle** quand le HUD est déployé — le HUD devient un
   mode, pas un décor permanent. Cohérent avec le principe JARVIS déjà
   retenu : *l'interface répond, elle n'est pas permanente*.
4. **Rendu à résolution interne réduite** puis mise à l'échelle
   (`scaling_3d_scale`) — à mesurer, jamais supposé.

La piste 3 est celle qui contredit le moins la direction déjà validée.

---

### Séquencement proposé — progressif, chaque étape testable

Cyril le dit lui-même : « à séquencer, pas un ajustement rapide ».

| Étape | Contenu | Pourquoi dans cet ordre |
|---|---|---|
| **A** | Remplacer les 3 sphères par un **mesh de tête humanoïde low-poly** | C'est l'écart structurel. Sans géométrie, aucun shader ne produira un visage. |
| **B** | Shader hologramme translucide (SciFi Hologram MIT / Wireframe CC0, §3) + **yeux émissifs** | Ne peut se juger qu'une fois la géométrie en place |
| **C** | Jauges **circulaires** (`draw_arc`), visualiseur d'onde, horloge large | Le HUD existe déjà en linéaire — évolution, pas création |
| **D** | HUD immersif plein écran | **Bloqué par les deux conflits ci-dessus.** N'ouvrir qu'après arbitrage VRAM et GDExtension. |

⚠️ **Le fallback reste ouvert** : `CLAUDE.md` et la décision du 02/08 posent
que si le rendu Godot déçoit après un vrai effort, **le 2D QPainter reste la
version stable** — ce n'est pas un échec, c'est l'option prévue depuis le
début. L'avatar sphère actuel et le HUD masqué sont les états
intermédiaires stables.

---

## 2. Spécification de comportement (origine Three.js)

⚠️ **À ne jamais porter tel quel** — mauvaise technologie, le projet est en
**Godot 4 / GDScript** (règle absolue n° 2 de `CLAUDE.md`). Ce qui suit décrit
le **comportement à reproduire nativement**, pas du code à traduire. Le code
source lui-même n'a pas été transmis (voir §0).

| Comportement | Transposition Godot |
|---|---|
| **Visage en nuage de points**, pas de mesh lourd | `GPUParticles3D` ou `MultiMeshInstance3D`, ou un mesh en mode `PRIMITIVE_POINTS`. L'intérêt annoncé — légèreté — est **à vérifier par la mesure** sur cette machine, pas à supposer. |
| **Transition d'opacité fluide 0.0 → 0.8** à l'activation/désactivation | `Tween` sur `modulate:a` (le mécanisme existe déjà dans `auto_hide.gd`). **Cohérent avec la leçon §5.67** : l'avatar ne doit pas être une présence permanente plein écran. |
| **Déformation du nuage par fonctions sinusoïdales** quand actif (« calcul / parole »), **retour élastique au repos** | Shader de sommets. ⚠️ **Attention au piège déjà documenté** (§ dérive organique, `main.gd`) : des sinusoïdes seules ont produit un mouvement **robotique**, parce que sur une fenêtre courte la dérivée d'une sinusoïde lente est constante. Le correctif retenu fut le **bruit fractal (fBm)**. Ne pas refaire l'erreur en repartant de sinusoïdes pures. |
| **Fenêtres avec flou d'arrière-plan** (`backdrop-filter`) | `BackBufferCopy` + shader de flou sur un `Panel` semi-transparent. Aucun équivalent direct : à construire. |

**Le quatrième point est le plus coûteux** et n'a jamais été évalué sur cette
machine — à mesurer avant de l'engager.

---

## 3. Deux shaders Godot repérés — licences à revérifier à l'usage

Sourcés par Cyril. **Non vérifiés indépendamment** : ni les URL, ni les
licences, ni le comportement réel n'ont été contrôlés depuis ce poste. À
revalider au moment de les intégrer — une page peut bouger, une licence
changer.

### SciFi Hologram — *KubikPixel*, annoncé **MIT**

`https://godotshaders.com/shader/scifi-hologram/`
Démo : `https://www.youtube.com/watch?v=ULAOwAOQtG8`

Lignes de scan, lueur Fresnel réglable, scintillement.

### Wireframe hologram shader — *DustedRobots*, annoncé **CC0**

`https://godotshaders.com/shader/wireframe-hologram-shader/`

S'applique directement sur un `MeshInstance3D`, couleur réglable,
glitch / rotation / flottement.

➜ **Le plus proche de ce que décrit Cyril**, et il rejoint mot pour mot la
Phase 1 déjà écrite dans `IDEAS.md` : *« LookDev & shaders sci-fi (fil de fer
glowing, particules) »*.

⚠️ **Le projet a déjà trois shaders** : `hologram.gdshader` (84 l.),
`grid.gdshader` (31 l.), `neon_border.gdshader` (35 l.). **Les lire avant
d'importer quoi que ce soit** — il se peut qu'une partie du besoin soit déjà
couverte.

---

## 4. Questions ouvertes — explicitement NON tranchées

**À ne pas construire. À rouvrir en session dédiée, sur décision explicite de
Cyril.**

### Intégration Astra (perception continue)

**Différée**, et la raison tient toujours : `VISION_LONG_TERME.md` §4.1 — *la
liberté d'action de Luca's est conditionnée à sa capacité de protection*. La
sécurité n'est pas assez mûre. **Ne pas rouvrir sans nouvelle décision
explicite.**

État réel du prérequis, mesuré le 06/08 (§5.66) : le **daemon de sécurité ne
tourne pas** — dernier balayage le 01/08, aucune tâche planifiée. Le niveau 1
est construit et testé (94 tests) mais **n'observe rien**. Tant que c'est le
cas, la condition de §4.1 n'est pas remplie.

### « GPT Live » / API vocale temps réel cloud pour le mobile

**En tension directe** avec un choix déjà mesuré et validé : `faster-whisper`
retenu le **01/08/2026** pour tourner **en CPU**, précisément afin de ne pas se
disputer la VRAM avec Ollama.

La tension n'est pas seulement technique, elle est **doctrinale** : une API
vocale temps réel cloud envoie **le flux audio continu** hors de la machine.
Cela relève directement de la règle 3 de `CLAUDE.md` (local par défaut, cloud
en exception) et du cas 1 du périmètre d'autonomie (**tout ce qui touche à
l'envoi de données hors de la machine revient à Cyril avant d'agir**).

**Documenté comme question. Non tranché.**

---

## 5. Point de départ concret pour la prochaine session

Ce qui existe déjà et qu'il ne faut pas reconstruire :

| Élément | État |
|---|---|
| `scenes/face/face_controller.gd` (195 l.) | 4 états, saccades, dérive fBm, suivi de souris (**axe Y corrigé le 07/08**) |
| `shaders/hologram · grid · neon_border` | 84 + 31 + 35 lignes, à relire avant d'importer |
| `scripts/_expr.gd` | Outil de **planche des 4 expressions** — c'est lui qui a trouvé la bouche invisible et les yeux asymétriques le 02/08. Mode d'emploi en tête du fichier. |
| HUD complet (`hud_canvas.tscn`, 271 l. + 5 widgets) | **Masqué** depuis le 07/08 (`_masquer_hud()`), pas supprimé — réversible en une ligne |
| Fenêtre 600×600 en coin | Validée par Cyril le 07/08 |
| `demos/lancer_lucas3d.ps1` / `arreter_lucas3d.bat` | Lancement propre (sortie redirigée) et **filet de sécurité testé** |

**Quatre défauts de rendu ont déjà été trouvés et corrigés le 02/08** — bouche
invisible, yeux asymétriques (5-7 %), `watching` jamais émis, inclinaison
imperceptible. Tous **invisibles au simple coup d'œil**, tous trouvés **en
mesurant**. C'est la méthode à reprendre, pas l'appréciation à l'œil.

⚠️ **`WATCHING` est le témoin de capture d'écran** — l'équivalent de la LED
d'une webcam, acté comme signal de confidentialité. Toute refonte visuelle doit
le préserver.

---

*Consolidé le 07/08/2026. Sources : `VISION_LONG_TERME.md` §2 et §4.1,
`IDEAS.md` (module Avatar, #95), `ROADMAP.md` §3, §5.66, §5.67.*
