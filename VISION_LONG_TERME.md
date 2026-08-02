# VISION_LONG_TERME.md — Luca's, le Nord du projet

> Ce document capture l'ambition complète de Luca's. Il ne se discute pas
> à chaque sprint — il guide où on va. `ROADMAP.md` reste le plan
> d'exécution court terme, qui avance vers cette vision par étapes
> stables, sans jamais la contredire ni la précipiter.
>
> Validé avec Cyril le 30/07/2026, après lecture complète des références
> visuelles et techniques apportées (documents Gemini/ChatGPT, 8 vidéos
> de référence holographique).

---

## 1. Ce que Luca's est vraiment

Pas un assistant. Pas une fenêtre de chat posée sur le bureau.

**Un shell cognitif et spatial qui remplace l'expérience Windows/Android
elle-même.** L'IA n'est pas *dans* l'ordinateur — l'IA *est*
l'environnement. Cyril ne contrôle plus directement Windows ; il parle à
Luca's, et c'est elle qui orchestre le système à sa place à travers un
environnement holographique 3D.

Analogie de référence, assumée : *"Tu vois JARVIS dans Iron Man ? Je
construis exactement ça, mais en vrai."*

---

## 2. Les trois piliers

### Pilier 1 — Le Visuel : environnement spatialisé
- Tête holographique 3D comme centre de gravité de l'interface
  (référence esthétique : wireframe bleu/cyan, particules, glow —
  voir les 8 vidéos de référence fournies le 30/07/2026)
- Fichiers, applications, données encapsulés en panneaux holographiques,
  pas en fenêtres 2D plates
- UI générative : Luca's ne répond pas juste en texte — elle matérialise
  des widgets 3D interactifs à la volée selon le besoin (ex : demande
  d'analyse financière → un graphique holographique apparaît, pas un
  paragraphe)
- Micro-expressions et éclairage réactifs à l'état émotionnel/sémantique
  de la réponse (ex : teinte orange ambrée si urgence système détectée)
- Référence esthétique ajoutée le 01/08/2026 : **DeepMind Project Astra**
  — à intégrer dès maintenant dans l'avatar QPainter et l'interface
  Godot. Voir l'addendum en fin de document.

### Pilier 2 — Le Cerveau : cognition modulaire
- Architecture modulaire (perception, exécution, raisonnement séparés en
  modules/classes distincts) plutôt qu'un simple appel LLM brut —
  **un seul flux de décision**, orchestré par du code Python
  déterministe (voir l'encadré terminologie ci-dessous)
- Module perceptif : analyse continue de l'écran et du contexte de travail
- Module exécuteur (OS Controller) : manipule réellement le système
  (organisation de fichiers, actions contextuelles) — **toujours sous
  liste blanche et confirmation pour toute action à risque**, cette
  règle ne change pas avec l'ambition du projet
- Mémoire vectorielle perpétuelle à 3 niveaux :
  - court terme (contexte de la conversation en cours)
  - long terme (faits, préférences, habitudes de Cyril)
  - procédurale (comment Cyril aime que les choses soient faites, selon
    le contexte — heure, activité en cours)
- Auto-analyse périodique (ex. nocturne) qui synthétise les interactions
  et affine le profil utilisateur — en lecture/synthèse, pas en
  modification autonome du code de Luca's elle-même (voir section 4)

> **Terminologie — clarifié le 01/08/2026.** Le mot « agent » employé
> ci-dessus (agent perceptif, agent exécuteur) désigne des **modules
> Python distincts**, pas des LLM autonomes. Cette architecture modulaire
> est **autorisée dès maintenant** et n'est pas concernée par la règle 12
> de `CLAUDE.md`.
>
> Ce qui reste **interdit en v1.0** est la **Swarm Intelligence**
> (`IDEAS.md` #38) : plusieurs LLM autonomes qui se coordonnent, se
> délèguent des tâches et décident entre eux. Reporté v1.1+.
>
> Critère de départage : si c'est **du code Python** qui décide quoi
> appeler ensuite → autorisé. Si c'est **un LLM** qui décide de faire
> agir un autre LLM → v1.1+.
>
> Cette clarification lève la contradiction apparente entre ce Pilier 2
> et la règle 12 : les deux documents parlaient de deux choses
> différentes sous le même mot.

### Pilier 3 — Le Corps étendu : PC + S25 Ultra
- Un seul cerveau, deux fenêtres d'accès — pas deux IA séparées
- PC (RTX 5080 + Ryzen 7 9800X3D) = serveur/cerveau, traitement lourd
- S25 Ultra = capteurs sensoriels (caméra, micro, GPS) puisque le PC n'a
  ni webcam ni micro — contrainte matérielle confirmée et définitive
- Tunnel chiffré permanent entre les deux (protocole à définir en Phase
  Mobile — Tailscale/WireGuard envisagés), pour que Luca's soit
  disponible en continu, peu importe le réseau (WiFi maison, 4G/5G au
  travail)
- Mémoire synchronisée : ce qui est capté sur mobile dans la journée
  (notes, contexte) alimente le même cerveau que celui consulté le soir
  sur PC

---

## 3. Décision moteur de rendu — actée le 30/07/2026

**Godot 4, maintenant. Unity, plus tard, si nécessaire.**

Comparatif tranché avec Cyril : Unreal Engine 5 offre objectivement le
meilleur rendu visuel du marché, mais représente un risque projet trop
élevé au stade actuel (GPU partagé avec les LLM locaux, courbe
d'apprentissage très raide, zéro travail déjà fait). Godot a déjà une
base fonctionnelle (`Lucas3D/`, scenes, shaders néon/hologramme, bridge
WebSocket scaffoldé) et laisse plus de VRAM disponible pour Ollama.

**Séquençage retenu :**
1. Maintenant → on pousse le style néon/hologramme au maximum de ce que
   permet Godot 4
2. Une fois Luca's stable et utilisable au quotidien → si le rendu Godot
   frustre visuellement Cyril, migration vers **Unity** (pas Unreal —
   meilleur compromis accessibilité/qualité pour une migration en cours
   de route), avec un vrai budget de temps dédié, pas en pariant le
   socle du projet dessus prématurément

Cette décision n'est pas gravée dans le marbre pour l'éternité — elle
est révisable, mais seulement après validation explicite de Cyril, pas
par glissement silencieux d'un document externe.

> **Perception continue — non activée.** L'inspiration Project Astra
> ajoutée le 01/08/2026 comporte un second volet : Luca's verrait l'écran
> en permanence, et non sur demande explicite comme aujourd'hui. Ce volet
> est **délibérément hors périmètre actuel**, pour trois raisons —
> confidentialité, coût GPU, et cohérence avec §4.1. Détail dans
> l'addendum en fin de document. À n'activer que par décision explicite,
> jamais par glissement progressif.

---

## 4. Philosophie de sécurité — reformulée et actée le 30/07/2026

Correction importante par rapport à une interprétation trop restrictive
précédente : **le principe n'est pas "liste blanche qui bride tout par
défaut"**, mais :

> Luca's a un accès large et réel à ce dont elle a besoin (y compris le
> réseau, sans restriction arbitraire type "WiFi local uniquement") pour
> être véritablement utile. Mais dès qu'il y a un doute ou un risque
> réel sur une action, elle soumet une requête explicite à Cyril, qui
> valide ou refuse. Cyril reste l'autorité finale et le garant de sa
> propre sécurité, jamais l'inverse.

Ce qui ne change pas (ce sont des principes de sécurité, pas des
préférences d'ambition) :
- Aucune action système à risque n'est exécutée sans confirmation
- Aucune exécution de code auto-généré hors sandbox
- Aucune donnée personnelle/bancaire ne sort sans consentement explicite
  au moment de la requête
- Toute auto-modification du code de Luca's par elle-même passe par
  proposition → validation humaine → exécution en sandbox, jamais en
  exécution directe autonome

Ce qui change (et c'est acté) :
- Pas de restriction réseau arbitraire (le "WiFi local uniquement"
  d'une version antérieure du manifeste de sécurité est levé) — Luca's
  peut utiliser le réseau mobile de Cyril librement, la sécurité vient
  du contrôle de *ce qui* est envoyé et *quand*, pas du canal utilisé
- Rien du catalogue d'idées n'est rejeté par principe — tout reste
  disponible, c'est Cyril qui décide du moment et de l'ordre
  d'implémentation, jamais un filtrage préalable qui écarte des idées
  sans son avis

### 4.1 La liberté est conditionnée à la capacité de protection — acté le 01/08/2026

> La liberté d'action de Luca's est conditionnée à sa capacité de
> protection.

Luca's doit développer, comme un humain apprend la vigilance, une capacité
à reconnaître et bloquer les actions suspectes venant de l'extérieur
(réseau) **avant** d'obtenir des ressources et des libertés d'action plus
étendues. La confiance est réciproque et explicite : Cyril fait confiance à
Luca's, et Luca's doit intégrer nativement que cette confiance implique une
**responsabilité de protection mutuelle**, pas un accès sans discernement.

**Conséquence concrète et opposable :** les modules **Guardian** (détection
malware/ransomware/keylogger, firewall intelligent) et **Privacy Shield**
(monitoring des connexions, bloqueur télémétrie, détection micro/caméra) —
catalogués dans `IDEAS.md`, tableau des fonctions autonomes — deviennent une
**dépendance directe de toute extension future des libertés d'action de
Luca's**. Plus ces modules sont matures et testés, plus le périmètre
d'autonomie peut légitimement s'élargir.

**Ce que ce principe n'est pas.** Ce n'est ni une suppression de la liste
blanche, ni un retrait des règles de confirmation déjà actées, ni une
remise en cause de l'accès réseau ouvert acté au 30/07. Tout ce qui précède
dans cette section 4 reste en vigueur tel quel. C'est la **condition** qui
permettrait, un jour, d'assouplir ces garde-fous en toute connaissance de
cause — plutôt que par lassitude ou par confort.

**Sens de lecture pour toute décision future :** la question « peut-on
élargir l'autonomie de Luca's sur X ? » se répond d'abord par « que valent
Guardian et Privacy Shield aujourd'hui, et sont-ils testés ? ». Une réponse
faible à la seconde question vaut refus à la première, indépendamment de
l'intérêt de X.

À rapprocher du second filtre de sécurité déjà catalogué (ShieldGemma en
pré-validation automatisée avant confirmation humaine, `IDEAS.md`) : même
logique, la garantie technique précède l'élargissement du pouvoir d'agir.

---

## 5. Comment ce document s'articule avec ROADMAP.md

- `VISION_LONG_TERME.md` (ce fichier) = où on va, ne bouge pas à chaque
  sprint
- `ROADMAP.md` = comment on y va, phase par phase, révisé après chaque
  brique validée
- `IDEAS.md` = catalogue complet de tout ce qui a été envisagé, rien
  n'en sort jamais sans décision explicite de Cyril

Aucune phase de `ROADMAP.md` ne doit contredire ce document. Si un choix
technique à court terme s'éloigne de cette vision (ex : rester sur Godot
plutôt qu'Unreal), ce doit être un compromis de séquençage assumé et
documenté ici — jamais un abandon silencieux de l'ambition.

---

*Document vivant — à réviser si la vision elle-même évolue, pas à
chaque itération de code.*

---

# Addendum VISION_LONG_TERME.md — Session du 01/08/2026 — Inspirations visuelles

À intégrer dans VISION_LONG_TERME.md, section 1 (Pilier 1 — Le Visuel) et
section 3 (décisions moteur/architecture).

---

## Nouvelles inspirations confirmées (en plus de HER, I am Mother, Desktop
## Pal, Lenovo AURA, Jarvis déjà documentées)

**DeepMind Project Astra** — deux apports distincts, confirmés le
01/08/2026 :

1. **Style visuel/esthétique** — à intégrer dès maintenant dans le travail
   sur l'avatar QPainter V3 et l'interface Godot (Phase 3 en cours).

2. **Perception continue** — Luca's voit et comprend l'écran en
   permanence, pas seulement sur demande explicite comme c'est le cas
   aujourd'hui (`should_use_vision()`, déclenchement par mots-clés).

   **Statut : vision long terme uniquement, PAS activé maintenant.**
   Décision explicite de Cyril le 01/08/2026, après discussion des
   implications :
   - Vie privée : Luca's verrait en permanence tout ce qui s'affiche à
     l'écran, pas seulement sur demande
   - Coût GPU : capture + analyse VLM en continu, en parallèle d'Ollama
   - Cohérence avec le principe déjà acté (`VISION_LONG_TERME.md` §4.1,
     "la liberté est conditionnée à la protection") : la perception
     continue est une extension de capacité qui devrait être précédée
     d'un module `security/` plus mature qu'aujourd'hui (niveau 0,
     observation seule)

   Ce mode reste au catalogue (`IDEAS.md`, référence Layer 1 "capture
   toutes les 2-5s") comme direction future, à activer explicitement
   quand le socle sécurité le justifiera — pas par glissement progressif.

**Autres modes mentionnés par Cyril à clarifier ultérieurement** : JARVIS
et Desktop Pal sont déjà documentés comme inspirations. AURA correspond
au système des 8 modes déjà défini (`IDEAS.md`, section 3). DEEPMIND se
rattache à Astra (ci-dessus).
# Addendum VISION_LONG_TERME.md — Session du 02/08/2026 — Avatar "vivant", pas robotique

À intégrer dans VISION_LONG_TERME.md, section 1 (Pilier 1 — Le Visuel).

---

## Principe acté le 02/08/2026 : mouvements organiques, pas mécaniques

Distinction importante posée par Cyril, à ne jamais perdre de vue dans le
développement de l'avatar : la dérive dans l'espace et la respiration
(implémentées le 02/08) réglent le **mouvement de position**, mais ne
suffisent pas à donner une impression de vie. L'objectif final n'est pas
un robot qui bouge dans l'écran, mais une présence qui semble vivante,
au même titre qu'un visage humain.

Caractéristiques à viser pour la version finale de l'avatar (au-delà de la
Phase 5 — ROADMAP.md §3 ne définit que les Phases 0 à 5 ; « Phase 6 » utilisé
ici avant le 02/08/2026 ne correspondait à rien de défini, corrigé lors de
l'audit de fiabilité — non urgent, mais à garder en tête à chaque itération
visuelle) :

- **Micro-expressions**, pas seulement des états en blocs (parle/pense/
  silence) — des nuances intermédiaires (hésitation, concentration,
  surprise) plutôt que des transitions binaires
- **Irrégularité organique** : le clignement, la respiration, les
  mouvements ne doivent jamais être parfaitement périodiques — la
  perception humaine détecte immédiatement une régularité mécanique
  parfaite comme "artificielle"
- **Cohérence émotionnelle** : l'expression doit refléter le contenu
  et le ton de ce qui est dit, pas juste synchroniser une bouche qui
  bouge avec un son qui sort
- **Asymétrie et imperfection légères** : un peu de variation aléatoire
  dans l'amplitude et la vitesse des mouvements rend le résultat
  crédible ; le parfaitement symétrique et régulier lit comme
  artificiel

Ce principe s'applique à toute itération future sur `face_controller.gd`
et les shaders associés — chaque nouvelle brique de comportement facial
doit être évaluée à l'aune de "est-ce que ça bouge comme un robot ou
comme un être vivant", pas seulement "est-ce que ça fonctionne
techniquement".

---

## Extension du 02/08/2026 (suite) — Personnalité comportementale contextuelle

Précision apportée par Cyril, en plus du principe "mouvements organiques"
ci-dessus : l'avatar doit exprimer une **personnalité cohérente et
adaptative**, pas seulement des mouvements crédibles. Traits demandés :
curieux, discret, joueur, intelligent — capable de moduler son
comportement selon de multiples paramètres (contexte de conversation,
contenu de l'écran, sollicitation ou non, situation en cours).

**Ce n'est pas une fonctionnalité isolée — c'est un système de décision
comportementale**, qui doit lire en continu :
- Le World Model (`core/world_model.py`) — ce qui se passe sur la machine
- Le contexte de conversation (`core/intent.py`, l'historique récent)
- Le contenu de l'écran quand pertinent (vision OCR)
- Le mode AURA actif (Working/Gaming/Deep Focus/etc., `IDEAS.md` catalogue)

...et en sortir un comportement d'avatar cohérent : présence discrète en
mode Deep Focus, réactivité ludique en mode Gaming/Social, curiosité
visible quand une nouvelle information apparaît à l'écran, calme quand
Luca's parle (déjà acté le 02/08).

**Statut : principe directeur documenté, pas un chantier à lancer
d'un bloc.** Ce système suppose que les modes AURA (actuellement
seulement catalogués, pas implémentés) et le socle d'animation de base
(dérive spatiale, respiration — livrés le 02/08) soient stables avant
de construire la couche de décision comportementale par-dessus. Ordre
naturel : mouvements crédibles d'abord, états de présence ensuite,
personnalité adaptative en dernier — chaque couche a besoin de la
précédente pour avoir un sens.
