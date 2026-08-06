# ORION AI — DOCUMENT DE SPÉCIFICATIONS COMPLÈTES
**Pour Claude — Intelligence Artificielle Assistante de Développement**
**Version : 1.0 | Date : 28 Juillet 2026**

---

## VISION GLOBALE

Orion AI est un **système d'exploitation cognitif** — une couche d'intelligence vivante qui s'intercale entre l'utilisateur et Windows 11. Windows devient invisible ; Orion devient l'interface. L'objectif est de créer une IA aussi utile que l'utilisateur en devienne dépendant au quotidien.

**Inspirations :**
- **HER** — Relation personnelle, conversation naturelle, évolution émotionnelle
- **I am Mother** — Surveillance protectrice, décision autonome, éthique
- **Desktop Pal** — Visage flottant holographique, HUD, réactivité visuelle
- **Lenovo AURA** — 8 Smart Modes, context awareness, Smart Share
- **Jarvis (Iron Man)** — Interface HUD, proactivité, contrôle total

**Matériel cible :**
- **PC** : Ryzen 7 9800X3D + RTX 5080 (16 Go VRAM) — maître, traitements lourds
- **Mobile** : Galaxy S25 Ultra — client léger via PWA/FastAPI

**Stack technique validée :**
- **Python** (PySide6, FastAPI, Ollama) = cerveau, logique métier, OS control
- **Godot Engine 4** (GDScript) = corps 3D, interface holographique, avatar
- **Communication** : WebSocket/HTTP local JSON entre Python et Godot

---

## ARCHITECTURE EN 5 COUCHES

```
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 5 : INTERFACE VIVANTE (Godot 4 + PySide6)                  │
│ ├─ Avatar 3D Holographique (visage néon/cyan, flottant)          │
│ ├─ Bureau Sémantique 3D (fichiers par concept, pas dossiers)     │
│ ├─ Barre Orion (remplace la taskbar Windows)                     │
│ ├─ HUD Orbital (widgets flottants autour du visage)              │
│ └─ Overlay Contextuel (notifications, suggestions)               │
├─────────────────────────────────────────────────────────────────┤
│ LAYER 4 : ACTION & EXPRESSION                                    │
│ ├─ Voice Engine (TTS Piper/Kokoro + prosodie émotionnelle)       │
│ ├─ OS Controller (ouvrir apps, orga fichiers, raccourcis)        │
│ ├─ Visual Feedback (animations Godot selon état émotionnel)      │
│ └─ Automation (macros intelligentes, scripts auto)               │
├─────────────────────────────────────────────────────────────────┤
│ LAYER 3 : COGNITION & RAISONNEMENT                               │
│ ├─ Reasoning Engine (chain-of-thought, débat interne 3 personas) │
│ ├─ Semantic Engine (graphe de connaissances temps réel)          │
│ ├─ Prediction Engine (anticipation intentions, proactivité)      │
│ └─ Decision Engine (actions autonomes sur liste blanche)         │
├─────────────────────────────────────────────────────────────────┤
│ LAYER 2 : MÉMOIRE & WORLD MODEL                                  │
│ ├─ Memory Palace 2.0 (5 types de mémoire)                        │
│ ├─ World Model OS (état temps réel de Windows)                   │
│ ├─ Knowledge Graph (entités, relations, inférence)               │
│ └─ Context Window (mémoire active + RAG hybride)                 │
├─────────────────────────────────────────────────────────────────┤
│ LAYER 1 : PERCEPTION MULTI-SENSORIELLE                           │
│ ├─ Vision Écran (OCR + VLM local, capture toutes les 2-5s)       │
│ ├─ Audio (STT Whisper + VAD + détection émotion voix)            │
│ ├─ Système (hooks Windows : fenêtres, processus, URL)            │
│ ├─ Webcam (émotions, attention, fatigue via OpenCV)              │
│ └─ Input (rythme clavier/souris, patterns d'usage)               │
├─────────────────────────────────────────────────────────────────┤
│ CŒUR : LLM MULTI-MODÈLES (Ollama local, RTX 5080)                │
│ ├─ Principal : deepseek-coder:33b (raisonnement, code, chat)     │
│ ├─ Vision : internvl2 / llava:13b (analyse écran temps réel)     │
│ ├─ Rapide : qwen2.5:7b (réponses instantanées, routing)          │
│ ├─ Créatif : mistral-nemo (brainstorming, storytelling)          │
│ ├─ Memory : bge-m3 (embeddings RAG)                              │
│ └─ TTS : Kokoro / Piper (voix locale naturelle)                  │
├─────────────────────────────────────────────────────────────────┤
│ INFRASTRUCTURE                                                   │
│ ├─ FastAPI (serveur local, WebSocket temps réel)                 │
│ ├─ SQLite + ChromaDB (mémoire persistante)                       │
│ ├─ Redis (cache, pub/sub)                                        │
│ └─ Celery (file de tâches async)                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## LES 5 PILIERS COGNITIFS

### 1. World Model OS

Orion maintient un **modèle mental temps réel** du PC :
- Fenêtre active, onglet, URL, titre de page
- Processus en cours (CPU/RAM par app)
- Fichiers ouverts
- **Causalité** : "Tu as ouvert Chrome → tu vas probablement chercher quelque chose"
- **Temporalité** : "Hier à 14h tu travaillais sur budget.xlsx"

**Technique** : pywin32 + UI Automation + capture écran OCR/VLM toutes les 2-5s

### 2. Memory Palace 2.0 — 5 Types de Mémoire

| Type | Description | Exemple |
|---|---|---|
| Épisodique | Souvenirs d'événements | "Mardi tu as bloqué 2h sur un bug CSS" |
| Sémantique | Connaissances factuelles | "Tu préfères le dark mode, tu codes en Python" |
| Procédurale | Comment faire les choses | "Pour exporter CSV, tu passes par Excel → Données" |
| Émotionnelle | États émotionnels passés | "Tu étais stressé avant la réunion de 10h" |
| Prospective | Ce que tu dois faire | "Rappel : envoyer le mail à Marc avant 18h" |

### 3. Emotional Resonance

5 capteurs fusionnés en un score émotionnel temps réel :
- **Voix** : pitch, vitesse, pauses
- **Visage** : webcam analyse émotions
- **Texte** : sentiment analysis
- **Clavier** : rythme de frappe
- **Physiologie** : wearables Bluetooth (optionnel)

### 4. Proactivité HER

Orion n'attend pas. Elle :
- **Observe** : "Tu travailles depuis 3h sans pause"
- **Prédit** : "Dans 10 min tu as un meeting"
- **Suggère** : "Je vois que tu cherches 'regex Python' pour la 5e fois"
- **Agit** : "J'ai fermé les 12 onglets inutiles et organisé tes téléchargements"

### 5. Semantic Desktop

- Fichiers flottent par **sens** (projet, urgence, type, personne)
- Recherche naturelle : *"le document modifié hier soir sur le projet Orion"*
- Auto-organisation selon habitudes
- Visualisation 3D : fichiers liés proches spatialement

---

## INTERFACE — REMPLACER WINDOWS 11

### Barre Orion (remplace Taskbar)
- Input universel (texte/voix/geste)
- Quick Actions prédites (3 actions les plus probables)
- Mode vocal : maintien espace = dictée
- Context-aware selon app active

### Avatar 3D Holographique (Godot 4)
- Fenêtre **transparente, borderless, always-on-top, click-through**
- Visage low-poly stylisé, shaders néon cyan/bleu avec glow
- **Flottement organique** : oscillation, respiration, réaction événements
- **Animations** : parle (bouche), pense (yeux brillent), triste (violet), alerte (rouge)
- **HUD Orbital** : widgets flottants (CPU, RAM, météo, tâches)

### Les 8 Modes AURA Orion

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

## AUTONOMIE & SÉCURITÉ

| Fonction | Description |
|---|---|
| Self-Healing | Redémarrage auto, rollback version stable |
| Self-Optimizing | Switch modèle LLM selon charge GPU, cache, cleanup nocturne |
| Self-Learning | Corrections mémorisées, habit extraction, LoRA nocturne |
| Self-Decision | Liste blanche : ouvrir apps, rappels, fermer distractions, orga fichiers, backup, MAJ, nettoyage |
| Self-Aware | Métacognition, auto-évaluation, transparence décisions, introspection |
| Guardian | Détection malware/ransomware/keylogger, firewall intelligent |
| Privacy Shield | Monitoring connexions, bloqueur télémétrie, détection micro/caméra, chiffrement AES-256 |

---

## ÉTAT ACTUEL DU PROJET (28/07/2026)

### Modules déjà fonctionnels
1. ✅ Chat avec streaming QThread
2. ✅ Mémoire persistante (SQLite)
3. ✅ Module Finance CSV (import, catégorisation)
4. ✅ Module Web (scraping, recherche)
5. ✅ Module RAG (retrieval augmented generation)
6. ✅ Module TTS (text-to-speech)
7. ✅ FastAPI serveur local
8. ✅ Module Automation (scripts)
9. ✅ Module Vision (OCR basique)
10. ✅ Module Calculatrice
11. ✅ Avatar 2D QPainter (v2 créé)
12. ✅ Config deepseek-coder:33b

### Structure existante sur le PC

```
C:\OrionAI
├── main.py
├── config.py
├── config.json
├── requirements.txt
├── venv/
├── core/
├── memory/
├── ui/
└── data/ (SQLite)
```

### Problèmes connus
- Aider + Ollama 8B échoue sur fichiers >200 lignes (boucle infinie)
- Avatar 3D Godot en cours de développement (rendu non satisfaisant, en pause)
- Cursor installé mais quota IA épuisé

---

## FEUILLE DE ROUTE 8 SEMAINES (180h)

| Semaine | Focus | Livrable |
|---|---|---|
| **S1** | Perception | Screen watcher + OCR + hooks Windows + World Model basique |
| **S2** | Mémoire & Cognition | Memory Palace + RAG + Reasoning Engine + Semantic Desktop v1 |
| **S3** | Interface Godot | Avatar 3D + HUD + fenêtre transparente + click-through |
| **S4** | Voix & Émotion | TTS continu + STT + Emotional Resonance v1 |
| **S5** | Modes AURA | 8 Smart Modes + Barre Orion + proactivité basique |
| **S6** | Action OS | OS Controller complet + automation + Semantic Desktop v2 |
| **S7** | Polish & Bridge | Self-healing + mobile bridge S25 + sync |
| **S8** | Package | Installer + tests + doc + release v1.0 |

---

## EXCLUSIONS VALIDÉES

- ❌ Connexions bancaires directes (CSV uniquement)
- ❌ PyQt6 (PySide6 uniquement)
- ❌ Avatar 3D Unity/Unreal (Godot 4 uniquement)
- ❌ Voice cloning avancé / XTTS
- ❌ Multi-agents (Swarm Intelligence en v1.1+)
- ❌ Marketplace communautaire
- ❌ Support Braille

---

## ARCHITECTURE ADAPTATIVE PC vs MOBILE

| | PC (RTX 5080) | Mobile (S25 Ultra) |
|---|---|---|
| Avatar | QPainter riche + shaders GPU | CSS/SVG allégé |
| Modèles | Ollama lourd local | FastAPI bridge vers PC maître |
| Traitements | Locaux (OCR, VLM, TTS) | Via WebSocket vers PC |
| Interface | Godot 3D + PySide6 | PWA (Progressive Web App) |
| Rôle | Maître (cerveau + GPU) | Client léger (affichage + input) |

---

## LISTE EXHAUSTIVE DES IDÉES ÉTUDIÉES

### 🎮 Modules Fun & Wow
1. **Jarvis Total** — OCR+VLM+TTS continu, assistant omniprésent
2. **Matrix Live** — Shader écran vert style Matrix sur le bureau
3. **DJ Orion** — Musique générée selon activité (focus, détente, sport)
4. **Storyteller Interactif** — Histoire + images + musique + voix générées localement
5. **Time Travel** — Screenshots toutes les 30s indexés, remonter le temps visuellement
6. **Orion Artiste** — Dessin sur écran (overlay interactif)
7. **Compagnon de Jeu** — Analyse écran en temps réel + overlay coaching
8. **Prank Orion** — Blagues contextuelles intelligentes (modération)

### 🧠 Modules Cognitifs Avancés
9. **Orion Brain 3D** — Réseau de neurones visuel temps réel dans Godot
10. **Holographic Desktop** — Bureau 3D holographique navigable
11. **Neural Link** — Prédiction patterns utilisateur (anticipation comportement)
12. **Parallel Universe** — Simulation "et si" (conséquences décisions)
13. **Memory Palace 3D** — Palais mental navigable en 3D
14. **Dream Visualization** — Rêves nocturnes visualisés (si données disponibles)
15. **Emotional Resonance** — 5 capteurs : voix, visage, texte, clavier, physiologie

### 🔍 Modules Sémantiques
16. **Semantic Desktop** — Fichiers organisés par sens/concept, pas par dossiers
17. **Knowledge Graph Live 3D** — Graphe de connaissances temps réel en 3D
18. **Concept Mapping Auto** — Cartes conceptuelles auto-générées
19. **Semantic Search Universel** — Recherche par sens, pas par mots-clés
20. **Contextual Awareness** — Références implicites : "le truc" = bon truc

### 🤯 Modules Démentiels
21. **Orion Clone** — Imitation style+voix locale via LoRA+XTTS
22. **Reality AR Orion** — Webcam voit bureau réel, projette infos AR
23. **Predictive Desktop** — Prépare le bureau avant usage (ouvre apps, fichiers)
24. **Orion Cinema** — Films 2-3min générés localement (scénario+images+musique+voix)
25. **Synthetic Companion** — Personnages virtuels avec mémoire persistante
26. **Living Wallpaper** — Fond d'écran vivant réactif à l'activité
27. **Orion Ghost** — Mode invisible, interventions critiques uniquement
28. **Data Sculpture** — Données transformées en sculptures 3D imprimables

### 🚀 Modules Futuristes (Inspirés Lenovo/Desktop Pal)
29. **Quantum Core** — Interface quantique simulée (visualisation qubits)
30. **Bio-Sync** — Rythme biologique réel (sommeil, cycles circadiens)
31. **Ambient Intelligence** — Qira : IA invisible dans l'espace (pas d'interface visible)
32. **Neural Mirror** — Workmate : projection sur surfaces/hologramme
33. **Body Double** — Tiko : compagnon travail pomodoro intelligent
34. **Modular Interface** — ThinkBook : blocs d'interface clipables
35. **Aura System** — 8 modes auto (Working/Creating/Meeting/Gaming/Entertainment/Learning/Social/Deep Focus)
36. **Smart Glasses Bridge** — Prêt pour lunettes AR (API standardisée)
37. **Digital Twin** — Jumeau numérique 3D du PC (diagnostic, prédiction pannes)
38. **Swarm Intelligence** — Multi-Orion parallèle : Principal, Analyste, Créatif, Veilleur, Apprenant

### 💰 Module Finance
39. **Import universel** CSV/OFX/QIF toutes banques françaises
40. **Catégorisation auto** par LLM
41. **Dashboard Wall Street** — Patrimoine, graphiques, ticker, allocation
42. **Analyse IA portefeuille** — Répartition, risque, corrélation, rebalancing, frais, fiscalité
43. **Scoring ESG** — Environnement, Social, Gouvernance
44. **Analyse technique & ML locale** — MM, RSI, MACD, patterns, prédiction scikit-learn
45. **Budget intelligent** — Prévisions, comparaisons, objectifs épargne
46. **Détecteur d'économies** — Abonnements inutilisés, doublons
47. **Simulateur scénarios** — Épargne, crédit, inflation, retraite
48. **Alertes prix & proactives**
49. **Rapports auto** mensuels/annuels/fiscaux/ESG export PDF/CSV/Excel

### 🏠 Domotique & Maison
50. **Home** — Hue, Sonos, thermostat, prises, capteurs, scénarios, routines matin/nuit
51. **Smart Mirror** — Infos matin, fitness, mode, santé, news

### 🎮 Gaming & Social
52. **Game Master** — JDR textuel, escape game, quiz personnalisé, trivia, speedrun, défis
53. **Party Mode** — Playlist collaborative QR, blind test, karaoké, photobooth, trivia soirée, RGB fête
54. **Cinema Club** — Recommandations locales, résumés sans spoilers, watchlist, notes, trivia

### 📱 Mobile Avancé
55. **Mobile Companion** — 8 modes auto (poche/table/conduite/marche/sport/cuisine/lecture/sommeil)
56. **AR Mobile** — Scan QR intelligent, reconnaissance objets/plantes/nourriture, traduction caméra, mode musée

### 🌐 Connectivité
57. **Mesh Network** — Partage fichiers/clipboard/écran entre appareils locaux, Orion distribuée PC→laptop→mobile, failover, sync delta
58. **Offline First** — Cartes OpenStreetMap, Wikipedia Kiwix, traduction Opus-MT, indexation pages favorites, 100% local

### 🧠 Cognition Avancée
59. **Reasoning Engine** — Chain-of-thought visible, débat interne 3 personas, analyse multi-critères, preuves et sources, logique floue, arbre décision 3D
60. **Knowledge Builder** — Auto-summarization, concept extraction, gap detection, synthesis, learning path, flashcards auto
61. **Creative Engine** — Brainstorming 20 idées, mashup generator, constraint solver, inspiration feed daily, collaborative writing, world building, music collaboration

---

## SPÉCIFICATIONS TECHNIQUES DÉTAILLÉES

### Modèles LLM (Ollama)

| Rôle | Modèle | Taille VRAM | Usage |
|---|---|---|---|
| Principal | deepseek-coder:33b | ~20 Go | Raisonnement, code, chat |
| Vision | internvl2 / llava:13b | ~8 Go | Analyse écran temps réel |
| Rapide | qwen2.5:7b | ~5 Go | Réponses instantanées, routing |
| Créatif | mistral-nemo | ~7 Go | Brainstorming, storytelling |
| Memory | bge-m3 | ~2 Go | Embeddings RAG |

### Communication Python ↔ Godot
- **WebSocket** : temps réel, bidirectionnel
- **Format** : JSON structuré
- **Exemple** : `{"type": "emotion", "data": {"state": "thinking", "intensity": 0.8}}`

### Base de données
- **SQLite** : données structurées (mémoire, config, historique)
- **ChromaDB** : vecteurs pour RAG
- **Redis** : cache, pub/sub, état temps réel

### Sécurité
- Chiffrement AES-256 pour données sensibles
- Sandbox pour exécution code auto-généré
- Liste blanche stricte pour actions autonomes

---

## NOTES POUR CLAUDE

1. **L'utilisateur est débutant** mais très motivé (2-4h/jour + week-ends). Privilégier la pédagogie et la compréhension sur la copie aveugle.
2. **Approche itérative** : livrer rapidement une version utilisable, puis itérer. Objectif : chat fluide + UI dark dès semaine 2-3.
3. **Carte blanche totale** : l'utilisateur a donné carte blanche. Tu peux modifier, améliorer, ajouter tout ce qui rend l'app meilleure sans demander permission.
4. **Streaming par blocs** : pour alléger l'UI, envoyer le texte par blocs de phrases plutôt que mot par mot.
5. **Architecture adaptative** : PC maître (GPU lourd), mobile client léger. Même logique métier, rendu adaptatif.
6. **Priorité actuelle** : la Couche Perception (S1) est le fondement. Sans elle, Orion est aveugle.

---

*Document généré par Kimi pour Claude — Orion AI Project*
*"L'intelligence ne se contente pas de répondre. Elle anticipe, elle comprend, elle évolue."*
