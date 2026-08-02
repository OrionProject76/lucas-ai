# IDEAS.md — Réservoir exhaustif d'idées, Luca's (ex-OrionAI)

> **Fichier reconstitué le 01/08/2026** — perdu du disque lors des
> manipulations de dossiers de la semaine passée (probablement non inclus
> dans le zip de backup utilisé pour récupérer `core/`/`ui/`). Contenu
> restauré depuis l'historique de conversation, à l'identique de
> l'original + l'addendum du 30/07 qui n'avait jamais pu être intégré
> faute de fichier cible.

Ce fichier recense 100% de la matière discutée : toutes les fonctionnalités envisagées, les pistes techniques, les alternatives écartées, et les exigences précises formulées. Rien ici n'est à considérer comme "décidé pour la roadmap immédiate" — c'est le catalogue complet dans lequel piocher, voir `ROADMAP.md` pour l'ordre réel de mise en œuvre.

**Principe non-négociable (acté le 30/07/2026)** : rien dans ce catalogue n'est rejeté par défaut. Tout reste disponible pour implémentation future. C'est Cyril qui décide du moment et de l'ordre, jamais un filtrage préalable qui écarte une idée sans son avis explicite.

---

## 1. Architecture cible en 5 couches

```
LAYER 5 : INTERFACE VIVANTE (Godot 4 + PySide6)
├─ Avatar 3D Holographique (visage néon/cyan, flottant)
├─ Bureau Sémantique 3D (fichiers par concept, pas dossiers)
├─ Barre Luca's (remplace la taskbar Windows)
├─ HUD Orbital (widgets flottants autour du visage)
└─ Overlay Contextuel (notifications, suggestions)

LAYER 4 : ACTION & EXPRESSION
├─ Voice Engine (TTS Piper/Kokoro + prosodie émotionnelle)
├─ OS Controller (ouvrir apps, orga fichiers, raccourcis)
├─ Visual Feedback (animations Godot selon état émotionnel)
└─ Automation (macros intelligentes, scripts auto)

LAYER 3 : COGNITION & RAISONNEMENT
├─ Reasoning Engine (chain-of-thought, débat interne 3 personas)
├─ Semantic Engine (graphe de connaissances temps réel)
├─ Prediction Engine (anticipation intentions, proactivité)
└─ Decision Engine (actions autonomes sur liste blanche)

LAYER 2 : MÉMOIRE & WORLD MODEL
├─ Memory Palace 2.0 (5 types de mémoire)
├─ World Model OS (état temps réel de Windows)
├─ Knowledge Graph (entités, relations, inférence)
└─ Context Window (mémoire active + RAG hybride)

LAYER 1 : PERCEPTION MULTI-SENSORIELLE
├─ Vision Écran (OCR + VLM local, capture toutes les 2-5s)
├─ Audio (STT Whisper + VAD + détection émotion voix)
├─ Système (hooks Windows : fenêtres, processus, URL)
├─ Webcam (émotions, attention, fatigue via OpenCV)
└─ Input (rythme clavier/souris, patterns d'usage)

CŒUR : LLM MULTI-MODÈLES (Ollama local, RTX 5080)
INFRASTRUCTURE : FastAPI, SQLite + ChromaDB, Redis, Celery
```

**Note du 01/08/2026** : voir `CLAUDE.md` règle 12 et `VISION_LONG_TERME.md`
encadré terminologie — cette architecture en couches/modules est une
architecture **modulaire** (code Python déterministe qui orchestre des
modules séparés), pas du Swarm Intelligence (#38 ci-dessous, toujours
reporté v1.1+).

---

## 2. Les 5 piliers cognitifs

1. **World Model OS** — modèle mental temps réel du PC (fenêtre active, onglet, URL, processus CPU/RAM, fichiers ouverts, causalité "tu as ouvert Chrome → tu vas chercher quelque chose", temporalité "hier à 14h tu travaillais sur budget.xlsx"). Technique : pywin32 + UI Automation + capture écran OCR/VLM toutes les 2-5s. **Statut : v1 simple implémentée (`core/world_model.py`), snapshot CPU/RAM/fenêtre active, sans causalité/temporalité pour l'instant.**

2. **Memory Palace 2.0** — 5 types de mémoire :
   | Type | Description | Exemple |
   |---|---|---|
   | Épisodique | Souvenirs d'événements | "Mardi tu as bloqué 2h sur un bug CSS" |
   | Sémantique | Connaissances factuelles | "Tu préfères le dark mode, tu codes en Python" |
   | Procédurale | Comment faire les choses | "Pour exporter CSV, tu passes par Excel → Données" |
   | Émotionnelle | États émotionnels passés | "Tu étais stressé avant la réunion de 10h" |
   | Prospective | Ce que tu dois faire | "Rappel : envoyer le mail à Marc avant 18h" |

3. **Emotional Resonance** — 5 capteurs fusionnés en un score émotionnel temps réel : voix (pitch, vitesse, pauses), visage (webcam), texte (sentiment analysis), clavier (rythme de frappe), physiologie (wearables Bluetooth, optionnel).

4. **Proactivité HER** — Observe ("tu travailles depuis 3h sans pause"), Prédit ("dans 10 min tu as un meeting"), Suggère ("je vois que tu cherches 'regex Python' pour la 5e fois"), Agit ("j'ai fermé les 12 onglets inutiles et organisé tes téléchargements").

5. **Semantic Desktop** — fichiers organisés par sens (projet, urgence, type, personne), recherche naturelle ("le document modifié hier soir sur le projet Luca's"), auto-organisation selon habitudes, visualisation 3D (fichiers liés proches spatialement).

---

## 3. Interface — remplacer Windows 11

### Barre Luca's (remplace la taskbar Windows)
- Input universel (texte/voix/geste)
- Quick Actions prédites (3 actions les plus probables)
- Mode vocal : maintien espace = dictée
- Context-aware selon app active

### Avatar 3D Holographique (Godot 4) — module détaillé
Fenêtre transparente, borderless, always-on-top, **click-through** (laisse passer les clics vers Windows en dessous).
Visage low-poly stylisé, shaders néon cyan/bleu avec glow. Flottement organique (oscillation, respiration, réaction événements). Animations : parle (bouche), pense (yeux brillent), triste (violet), alerte (rouge). HUD Orbital : widgets flottants (CPU, RAM, météo, tâches).

**Roadmap détaillée du module Avatar :**

- **Phase 1 — Assets**
  - Tête 3D cybernétique (`.gltf`/`.fbx`, style hologramme/robotique)
  - Blendshapes/Shape Keys (ouverture de bouche, clignement, expressions)
  - LookDev & shaders sci-fi (fil de fer glowing, particules)
  - Éclairage dynamique effet écran/hologramme

- **Phase 2 — Pipeline Lip-Sync & réactivité vocale**
  - Cartographie des visèmes : phonèmes TTS → shape keys de bouche
  - Librairie de lip-sync temps réel
  - Animations d'attente : clignements aléatoires, rotation légère, pulsation
  - États visuels : veille, écoute, réflexion, parole

- **Phase 3 — Moteur de rendu & fenêtre**
  - **Décision actée (30/07/2026, révisée 01/08) : Godot 4 pour l'instant, Unity en migration future si nécessaire** (Unreal écarté — trop coûteux en VRAM partagée avec Ollama, voir `VISION_LONG_TERME.md` §3)
  - Fenêtre borderless, fond transparent, superposée au bureau Windows

- **Phase 4 — Raccordement au "cerveau" (sockets/API)**
  - WebSocket unique `/ws` (déjà scaffoldé dans `api/server.py`)
  - `ON_LISTEN`, `ON_THINKING`, `ON_SPEAK`, `ON_ERROR`

- **Phase 5 — Optimisation & tests de performance**
  - Bridage FPS, optimisation polygones (GPU partagé avec Ollama)
  - Latence fin TTS → animation vocale, cible < 150ms

- **Ajouts identifiés en cours de route :**
  - Fallback avatar 2D (QPainter, déjà existant v2) si GPU trop chargé
  - Mode "avatar désactivé" auto si modèle lourd (deepseek-coder:33b) tourne
  - Mode "Debug Silencieux" : veille graphique totale pendant dev de Luca's elle-même

### Les 8 Modes AURA Luca's
| Mode | Déclencheur | Comportement |
|---|---|---|
| 🧑‍💻 Working | App pro ouverte | Focus max, notifs filtrées, raccourcis pro |
| 🎨 Creating | App créative | Mode inspiration, génération idées, mood board |
| 🤝 Meeting | Calendrier/visio | Transcription auto, résumé, action items |
| 🎮 Gaming | Jeu détecté | Perf boost, overlay compagnon, coaching |
| 🎬 Entertainment | Netflix/YouTube | Recommandations, ambiance lumière |
| 📚 Learning | Tutoriel/doc | Explications adaptatives, flashcards, quiz |
| 💬 Social | Messages/réseaux | Réponses suggérées, résumé conversations |
| 🧘 Deep Focus | Commande "focus" | Tout bloqué, musique lo-fi, compte à rebours |

---

## 4. Autonomie & sécurité

| Fonction | Description |
|---|---|
| Self-Healing | Redémarrage auto, rollback version stable |
| Self-Optimizing | Switch modèle LLM selon charge GPU, cache, cleanup nocturne |
| Self-Learning | Corrections mémorisées, habit extraction, LoRA nocturne |
| Self-Decision | Liste blanche : ouvrir apps, rappels, fermer distractions, orga fichiers, backup, MAJ, nettoyage |
| Self-Aware | Métacognition, auto-évaluation, transparence décisions, introspection |
| Guardian | Détection malware/ransomware/keylogger, firewall intelligent |
| Privacy Shield | Monitoring connexions, bloqueur télémétrie, détection micro/caméra, chiffrement AES-256 |
| **Second filtre de sécurité (ajout 31/07)** | ShieldGemma comme pré-validation automatisée avant confirmation humaine — voir `VISION_LONG_TERME.md` Pilier 2 |

---

## 5. Catalogue exhaustif des idées (66 idées d'origine + ajouts)

### 🎮 Modules fun & wow
1. Jarvis Total — OCR+VLM+TTS continu, assistant omniprésent
2. Matrix Live — Shader écran vert style Matrix sur le bureau
3. DJ Luca's — Musique générée selon activité (focus, détente, sport)
4. Storyteller Interactif — Histoire + images + musique + voix générées localement
5. Time Travel — Screenshots toutes les 30s indexés, remonter le temps visuellement
6. Luca's Artiste — Dessin sur écran (overlay interactif)
7. Compagnon de Jeu — Analyse écran temps réel + overlay coaching
8. Prank Luca's — Blagues contextuelles intelligentes (modération)

### 🧠 Modules cognitifs avancés
9. Luca's Brain 3D — Réseau de neurones visuel temps réel dans Godot
10. Holographic Desktop — Bureau 3D holographique navigable
11. Neural Link — Prédiction patterns utilisateur (anticipation comportement)
12. Parallel Universe — Simulation "et si" (conséquences décisions)
13. Memory Palace 3D — Palais mental navigable en 3D
14. Dream Visualization — Rêves nocturnes visualisés (si données disponibles)
15. Emotional Resonance — 5 capteurs : voix, visage, texte, clavier, physiologie

### 🔍 Modules sémantiques
16. Semantic Desktop — Fichiers organisés par sens/concept, pas par dossiers
17. Knowledge Graph Live 3D — Graphe de connaissances temps réel en 3D
18. Concept Mapping Auto — Cartes conceptuelles auto-générées
19. Semantic Search Universel — Recherche par sens, pas par mots-clés
20. Contextual Awareness — Références implicites : "le truc" = bon truc

### 🤯 Modules démentiels
21. Luca's Clone — Imitation style+voix locale via LoRA+XTTS *(voice cloning avancé/XTTS explicitement exclu — voir section 7)*
22. Reality AR Luca's — Webcam voit bureau réel, projette infos AR
23. Predictive Desktop — Prépare le bureau avant usage (ouvre apps, fichiers)
24. Luca's Cinema — Films 2-3min générés localement (scénario+images+musique+voix)
25. Synthetic Companion — Personnages virtuels avec mémoire persistante
26. Living Wallpaper — Fond d'écran vivant réactif à l'activité
27. Luca's Ghost — Mode invisible, interventions critiques uniquement
28. Data Sculpture — Données transformées en sculptures 3D imprimables

### 🚀 Modules futuristes (inspirés Lenovo/Desktop Pal)
29. Quantum Core — Interface quantique simulée (visualisation qubits)
30. Bio-Sync — Rythme biologique réel (sommeil, cycles circadiens)
31. Ambient Intelligence — IA invisible dans l'espace (pas d'interface visible)
32. Neural Mirror — Projection sur surfaces/hologramme
33. Body Double — Compagnon travail pomodoro intelligent
34. Modular Interface — Blocs d'interface clipables
35. Aura System — 8 modes auto (détaillés section 3)
36. Smart Glasses Bridge — Prêt pour lunettes AR (API standardisée)
37. Digital Twin — Jumeau numérique 3D du PC (diagnostic, prédiction pannes)
38. **Swarm Intelligence — Multi-Luca's parallèle : Principal, Analyste, Créatif, Veilleur, Apprenant.** *(Multi-agents LLM autonomes explicitement exclu de la v1, reporté v1.1+ — voir `CLAUDE.md` règle 12, clarifié le 01/08/2026 : c'est CETTE idée précisément qui est interdite, pas l'architecture modulaire du Pilier 2)*

### 💰 Module finance
39. Import universel CSV/OFX/QIF toutes banques françaises
40. Catégorisation auto par LLM
41. Dashboard Wall Street — Patrimoine, graphiques, ticker, allocation
42. Analyse IA portefeuille — Répartition, risque, corrélation, rebalancing, frais, fiscalité
43. Scoring ESG — Environnement, Social, Gouvernance
44. Analyse technique & ML locale — MM, RSI, MACD, patterns, prédiction scikit-learn
45. Budget intelligent — Prévisions, comparaisons, objectifs épargne
46. Détecteur d'économies — Abonnements inutilisés, doublons
47. Simulateur scénarios — Épargne, crédit, inflation, retraite
48. Alertes prix & proactives
49. Rapports auto mensuels/annuels/fiscaux/ESG export PDF/CSV/Excel — **pattern de référence validé 31/07 : nettoyage CSV → catégorisation → graphique → export, voir `VISION_LONG_TERME.md` §6**

### 🏠 Domotique & maison
50. Home — Hue, Sonos, thermostat, prises, capteurs, scénarios, routines matin/nuit
51. Smart Mirror — Infos matin, fitness, mode, santé, news

### 🎮 Gaming & social
52. Game Master — JDR textuel, escape game, quiz personnalisé, trivia, speedrun, défis
53. Party Mode — Playlist collaborative QR, blind test, karaoké, photobooth, trivia soirée, RGB fête
54. Cinema Club — Recommandations locales, résumés sans spoilers, watchlist, notes, trivia

### 📱 Mobile avancé
55. Mobile Companion — 8 modes auto (poche/table/conduite/marche/sport/cuisine/lecture/sommeil)
56. AR Mobile — Scan QR intelligent, reconnaissance objets/plantes/nourriture, traduction caméra, mode musée

### 🌐 Connectivité
57. Mesh Network — Partage fichiers/clipboard/écran entre appareils locaux, Luca's distribuée PC→laptop→mobile, failover, sync delta
58. Offline First — Cartes OpenStreetMap, Wikipedia Kiwix, traduction Opus-MT, indexation pages favorites, 100% local

### 🧠 Cognition avancée
59. Reasoning Engine — Chain-of-thought visible, débat interne 3 personas, analyse multi-critères, preuves et sources, logique floue, arbre décision 3D
60. Knowledge Builder — Auto-summarization, concept extraction, gap detection, synthesis, learning path, flashcards auto
61. Creative Engine — Brainstorming 20 idées, mashup generator, constraint solver, inspiration feed daily, collaborative writing, world building, music collaboration

### ✨ Ajouts session 28-31/07/2026
62. Mode "Garde/Poste" — détecte les horaires de travail postés et adapte la proactivité (silence pendant le travail, résumé au retour)
63. Assistant révision aide-soignant — flashcards et quiz générés localement à partir de supports de cours, pour accompagner une reconversion professionnelle
64. Vigilance budget temps réel — alerte douce en cas de dépassement d'un budget mensuel serré
65. Journal vocal fatigue/sommeil — auto-déclaratif uniquement, sans capteur santé externe requis, adapté à un métier physique
66. Mode "Debug Silencieux" — veille graphique totale de l'avatar pendant le développement de Luca's elle-même, pour libérer le GPU
67. **Suivi & validation à distance (S25 Ultra)** — Tailscale+terminal mobile, ou bot Telegram/Discord de notification+validation par boutons, ou workflow Git+PR GitHub. Rejoint #6 (Handoff PC↔S25) — à fusionner conceptuellement, pas dupliquer.
68. **Modèles spécialisés en complément** — Gemma Vision (VLM léger, analyse écran) et ShieldGemma (second filtre sécurité automatisé) en complément du modèle principal, chacun sur sa tâche plutôt qu'un seul modèle surchargé. Détaillé dans `VISION_LONG_TERME.md` Pilier 2.
69. **Contrainte matérielle confirmée** — pas de webcam/micro sur PC, tout ce qui nécessite caméra/micro passe obligatoirement par le S25 Ultra.

---

## 6. Spécifications techniques détaillées

### Base de données
- SQLite : données structurées (mémoire, config, historique) — **implémenté** (`memory/memory_manager.py`)
- ChromaDB : vecteurs pour RAG — **implémenté et validé 01/08/2026** (`modules/rag_manager.py`, embedding via Ollama nomic-embed-text)
- Redis : cache, pub/sub, état temps réel — pas encore en place
- Celery : file de tâches async — pas encore en place

### Sécurité
- Chiffrement AES-256 pour données sensibles
- Sandbox pour exécution de code auto-généré
- Liste blanche stricte pour actions autonomes, **assouplie en "accès large + confirmation sur risque"** (voir `VISION_LONG_TERME.md` §4, révisé 30/07/2026)

### Architecture adaptative PC vs Mobile
| | PC (RTX 5080) | Mobile (S25 Ultra) |
|---|---|---|
| Avatar | QPainter riche + shaders GPU | CSS/SVG allégé |
| Modèles | Ollama lourd local | FastAPI bridge vers PC |
| Traitements | Locaux (OCR, VLM, TTS) | Via WebSocket vers PC |
| Interface | Godot 3D + PySide6 | PWA |
| Rôle | Maître (cerveau + GPU) | Client léger (affichage + input) |
| **Synchro (précisé 31/07)** | **Hybride : auto sur événement + à la demande, conflit résolu par timestamp (dernier écrit gagne)** | idem |

---

## 7. Exclusions validées (à ne jamais réintroduire sans décision explicite)

- ❌ Connexions bancaires directes (CSV/OFX/QIF uniquement)
- ❌ PyQt6 (PySide6 uniquement)
- ❌ Avatar 3D Unreal Engine (Godot 4 maintenant, Unity en migration future possible — Unreal écarté, voir `VISION_LONG_TERME.md` §3)
- ❌ Voice cloning avancé / XTTS
- ❌ Swarm Intelligence (#38) en v1 — reporté v1.1+ (clarifié 01/08 : ne concerne QUE le multi-LLM autonome, pas l'architecture modulaire)
- ❌ Marketplace communautaire
- ❌ Support Braille

---

## 8. Notes non altérées / exigences précises exprimées

- L'utilisateur est débutant en développement mais très motivé (2-4h/jour + week-ends). Privilégier pédagogie et compréhension plutôt que copie aveugle de code.
- Approche itérative : livrer rapidement une version utilisable, puis itérer.
- Carte blanche totale donnée par l'utilisateur, mais rien n'est décidé sans en discuter — documenter les choix, ne jamais rejeter une idée du catalogue sans son avis explicite (principe acté 30/07/2026).
- Streaming du texte par blocs de phrases plutôt que mot par mot, pour alléger l'UI.
- Architecture adaptative : PC maître (GPU lourd), mobile client léger.
- Problèmes techniques rencontrés et documentés : Aider + Ollama 8B échoue sur fichiers >200 lignes ; quota IA Cursor épuisé, d'où passage à Claude Code.
- Documentation de référence technique existante côté utilisateur : "orion_ai_documentation.docx".
- **Renommage acté (29-30/07/2026)** : Orion → Luca's. Partie visible faite le 01/08/2026, renommage technique du code fait le 02/08/2026 (voir `ROADMAP.md` §6).

---

# Addendum IDEAS.md — Session du 02/08/2026 — Ambition mobile complète

À intégrer dans IDEAS.md, nouvelle sous-section du catalogue (section 5).

---

## 70. Centre de commande mobile S25 Ultra — vision complète

Capturé le 02/08/2026, à partir d'une session de brainstorming avec Cyril.
Catalogué dans son intégralité pour ne rien perdre — voir ROADMAP.md §2
pour ce qui est réellement en cours d'implémentation (périmètre restreint,
décidé le même jour).

### Modèles d'inspiration identifiés
- **Tasker + AutoVoice** — automatisation Android complète (lancer apps,
  simuler clics, requêtes web, domotique). Candidat sérieux pour ne pas
  reconstruire l'automatisation Android depuis zéro — dépendance tierce à
  évaluer le moment venu, pas une brique à coder soi-même.
- **Microsoft Copilot Voice / Google Gemini Live** — service Android en
  premier plan (Foreground Service) avec notification persistante, pour
  garder le micro en écoute passive du mot-clé "Luca" sans que l'OS ne
  tue l'app pour économiser la batterie.
- **Rabbit R1 / Humane AI Pin** — modèle "LAM" (Large Action Model) :
  l'IA n'exécute pas que des réponses textuelles, elle déclenche des
  scripts réels (recherche RAG vs action multimédia, décidé
  automatiquement selon la demande).

### Exemple d'orchestration cible : double action parallèle
Ordre vocal unique → deux agents en parallèle : un agent qui consulte un
document (RAG local sur le PC) et un agent qui déclenche une action sur
le PC (ex. lancer une app, changer de fenêtre) → résultat fusionné en une
seule réponse vocale + notification push. Illustre l'architecture
multi-agents (au sens modulaire, voir CLAUDE.md règle 12) appliquée à un
scénario mobile réel.

### Interface mobile idéale (S25 Ultra)
- Avatar 2D/3D léger (pas de scène 3D lourde — batterie), qui change de
  couleur/rythme selon les 5 modes de présence déjà existants côté serveur
- HUD d'action rapide : onglets directs vers Finance et Documents (RAG),
  déjà fonctionnels côté PC
- Mode bouton micro géant, en complément de l'écoute passive, pour les
  environnements bruyants

### Android Auto — contrainte technique majeure, à traiter à part
**Important, découvert en discutant le 02/08/2026** : Android Auto
n'autorise pas d'interface personnalisée libre pendant la conduite,
imposé par Google pour la sécurité routière. Seules certaines catégories
d'apps (musique, navigation, messagerie) ont un affichage via des
templates imposés par Google — un avatar/HUD personnalisé n'est
techniquement pas possible à afficher. Le reste ne peut passer que par de
l'interaction **vocale pure**, pas visuelle.

**Conséquence pour la roadmap** : Android Auto n'est pas une extension du
pont mobile de base — c'est une initiative distincte, à traiter une fois
la PWA de base stable, avec ses propres contraintes de plateforme à
étudier en détail le moment venu (probablement limité au vocal).

### Automatisation domotique/PC illustrative
Exemple donné : contrôle de la TV via navigateur (selenium/pyautogui) —
bon cas d'usage concret pour `OS Controller`/liste blanche (déjà au
catalogue), pas urgent, juste un exemple qui illustre bien le principe.

---

**Statut au 02/08/2026** : catalogué dans son ensemble. Le périmètre
réellement engagé maintenant est volontairement restreint — voir
ROADMAP.md §2 pour la brique de base (PWA chat + micro + avatar léger),
qui doit être stable et prouvée avant d'envisager Tasker, Android Auto,
ou l'automatisation domotique/PC.

---

# Addendum IDEAS.md / VISION_LONG_TERME.md — Session du 02/08/2026
# Écoute et vision contextuelles selon "maison" vs "dehors"

À intégrer dans IDEAS.md (nouvelle entrée catalogue) ET comme précision
dans VISION_LONG_TERME.md §4 (philosophie de sécurité).

---

## 71. Écoute/vision ambiante contextuelle — "chez moi" vs "dehors"

Clarification apportée par Cyril le 02/08/2026, en réponse à une
proposition d'écoute ambiante permanente généralisée (rejetée telle
quelle — voir ci-dessous pourquoi).

**Principe retenu, différent de "toujours écouter partout" :**
- **Contexte "à la maison"** (PC/avatar actif, Cyril chez lui) : micro du
  téléphone ouvert en continu, analyse sémantique ambiante active — pas
  besoin de mot-clé de déclenchement. Justification de Cyril : *"à la
  maison je n'ai rien à cacher"*.
- **Contexte "dehors"** (téléphone seul, hors de la maison) : activation
  strictement sur demande explicite (ex. "Luca, s'il te plaît"), jamais
  d'écoute ambiante en arrière-plan. Même logique pour la lecture
  d'écran/caméra : sur demande uniquement hors du contexte maison.

**Important — ceci N'EST PAS l'activation de la perception continue
Astra** discutée et explicitement refusée pour l'instant le 02/08/2026
(vision long terme, conditionnée à un `security/` plus mature). C'est
une distinction contextuelle plus fine, pas un retour sur cette décision.
Reste néanmoins un vrai changement de portée par rapport à ce qui existe
aujourd'hui (activation uniquement sur bouton/mot précis) — à ne pas
implémenter sans une nouvelle validation explicite le moment venu, avec
un plan concret.

### Problème technique non résolu, à garder en tête
Comment Luca's détermine-t-elle le contexte "maison" vs "dehors" ? Piste
la plus simple : détection du réseau WiFi connecté (domicile vs
autre/cellulaire). Pas tranché, pas urgent.

### Contrainte de performance à anticiper
Une écoute ambiante véritablement continue avec transcription complète
(Whisper tournant en permanence) serait coûteuse en calcul et en
batterie côté téléphone. La bonne architecture, le moment venu,
ressemblerait à la détection de mot-clé légère des assistants
commerciaux (un tout petit modèle "toujours actif" qui ne déclenche une
vraie transcription/analyse que sur une activité intéressante) plutôt
que Whisper qui tourne 24/7. À concevoir en détail quand ce chantier
sera vraiment lancé, pas maintenant.

---

## 72. Mécanisme de verrouillage en cas de compromission — idée mise en pause, PAS rejetée

Proposition initiale : auto-destruction de l'app mobile si compromission
détectée (root, extraction de code), réactivation possible uniquement
par reconnexion USB physique au PC.

**Statut le 02/08/2026 : mise en pause, pas abandonnée.** Risque identifié
par Claude (via Claude — vérifié avec Cyril) : un faux positif
(root légitime, mise à jour Android déclenchant une fausse alerte)
bloquerait Cyril hors de chez lui, sans accès à Luca's, jusqu'à un retour
physique — le mécanisme pourrait le pénaliser lui-même plus qu'un vrai
attaquant.

**À rechercher ensemble plus tard** : une alternative moins punitive —
par exemple une révocation à distance via les listes de contrôle d'accès
Tailscale plutôt qu'une auto-destruction, ou une confirmation par un
second canal avant tout verrouillage définitif.
