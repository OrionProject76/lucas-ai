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
base fonctionnelle (`Orion3D/`, scenes, shaders néon/hologramme, bridge
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
