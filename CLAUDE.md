# ORION AI — Contexte Projet pour Claude Code

## 🎯 Vision
Orion AI est un système d'exploitation cognitif — une couche d'intelligence vivante entre l'utilisateur et Windows 11. Windows devient invisible ; Orion devient l'interface.

## 🏛️ Architecture (5 couches)
```
Layer 5 : Interface Vivante (Godot 4 + PySide6)
Layer 4 : Action & Expression (TTS, OS Controller, Automation)
Layer 3 : Cognition & Raisonnement (Reasoning, Semantic, Prediction, Decision)
Layer 2 : Mémoire & World Model (Memory Palace 2.0, World Model OS, Knowledge Graph)
Layer 1 : Perception Multi-Sensorielle (Screen, Audio, System, Webcam, Input)
Cœur : LLM Multi-Modèles (Ollama local, RTX 5080)
```

## 🖥️ Matériel
- PC : Ryzen 7 9800X3D + RTX 5080 (16 Go VRAM) — maître
- Mobile : Galaxy S25 Ultra — client léger via PWA/FastAPI

## 📦 Stack Technique Validée
- **Python** : PySide6, FastAPI, Ollama, SQLite, ChromaDB, Redis
- **Godot 4** : GDScript, frontend 3D, avatar holographique
- **Communication** : WebSocket JSON local entre Python et Godot
- **Tests** : pytest avec coverage
- **Lint** : ruff + mypy
- **Task runner** : just (justfile à la racine)

## 🚫 Règles Absolues (NE JAMAIS ENFREINDRE)
1. **PySide6 uniquement** — PAS PyQt6
2. **Godot 4 uniquement** — PAS Unity/Unreal
3. **Ollama local uniquement** — PAS d'API cloud pour les LLM
4. **CSV uniquement** pour la finance — PAS de connexions bancaires directes
5. **Tout en anglais** : variables, fonctions, comments, docstrings
6. **Type hints obligatoires** sur toutes les fonctions
7. **Docstrings** pour chaque classe et fonction publique
8. **Tests unitaires** pour chaque module avec pytest
9. **Git commit** à chaque feature terminée avec message clair
10. **PAS d'avatar 3D Unity/Unreal** — Godot 4 seul
11. **PAS de voice cloning avancé/XTTS** — Piper/Kokoro seuls
12. **PAS de Swarm Intelligence** en v1.0 (plusieurs LLM autonomes coordonnés — `IDEAS.md` #38) — reporté v1.1+

### ⚠️ Précision sur la règle 12 — "multi-agents" (clarifié le 01/08/2026)

La règle 12 interdit **une seule chose** : la **Swarm Intelligence**, c'est-à-dire
plusieurs instances LLM autonomes qui se coordonnent entre elles, se délèguent des
tâches et décident ensemble (`IDEAS.md` #38). Reporté en v1.1+, car ça multiplie la
VRAM consommée, rend le débogage quasi impossible et retire à Cyril le point de
contrôle unique sur ce que fait Luca's.

Ce que la règle 12 **n'interdit pas**, et qui est **autorisé dès maintenant** :
une **architecture modulaire** où perception, exécution et raisonnement sont séparés
en modules/classes Python distincts, avec **un seul flux de décision** — un seul
appel LLM décisionnaire à la fois, orchestré par du code Python déterministe.

| Autorisé maintenant (architecture modulaire) | Interdit en v1.0 (Swarm) |
|---|---|
| `perception/`, `core/`, `automation/` en modules séparés | Deux LLM qui se parlent et se répondent |
| Code Python qui appelle le LLM puis route le résultat | Un LLM qui spawn/pilote un autre LLM |
| Plusieurs modèles Ollama pour des rôles différents (vision, chat, embeddings), appelés séquentiellement par le code | Agents concurrents avec négociation/consensus |
| Une classe `ReasoningEngine` qui enchaîne plusieurs prompts (chain-of-thought) | Boucle d'agents autonome sans point de contrôle humain |

**Test rapide** : si c'est **du code Python** qui décide quoi appeler ensuite → autorisé.
Si c'est **un LLM** qui décide de faire agir un autre LLM → interdit jusqu'en v1.1.

Le mot "agent" employé dans `VISION_LONG_TERME.md` (§2, Pilier 2 : « agent perceptif »,
« agent exécuteur ») désigne des **modules** au sens ci-dessus, pas des LLM autonomes —
la vision et la règle 12 ne se contredisent donc pas.

## 📁 Structure Dossiers
```
C:/OrionAI/
├── main.py                    # Point d'entrée FastAPI + PySide6
├── config.py                  # Configuration centralisée
├── config.json                # Config utilisateur (modifiable)
├── requirements.txt           # Dépendances principales
├── requirements_daemon.txt    # Dépendances daemon
├── justfile                   # Commandes rapides
├── CLAUDE.md                  # CE FICHIER
├── orion_daemon.py            # Daemon 24/7
├── orion_report.py            # Rapport matinal standalone
├── core/                      # Logique métier
│   ├── __init__.py
│   ├── llm_manager.py         # Gestion multi-modèles Ollama
│   ├── reasoning_engine.py    # Chain-of-thought, débat interne
│   └── decision_engine.py   # Actions autonomes liste blanche
├── perception/                # Couche 1 — Perception
│   ├── __init__.py
│   ├── screen_watcher.py      # Capture écran + OCR + VLM
│   ├── system_watcher.py      # Hooks Windows (fenêtres, processus)
│   ├── audio_watcher.py       # Micro + VAD + STT Whisper
│   ├── webcam_watcher.py      # Émotions + attention webcam
│   └── input_watcher.py       # Patterns clavier/souris
├── memory/                    # Couche 2 — Mémoire
│   ├── __init__.py
│   ├── memory_palace.py       # 5 types de mémoire
│   ├── world_model.py         # État temps réel OS
│   ├── knowledge_graph.py     # Graphe entités/relation
│   ├── rag_engine.py          # Retrieval Augmented Generation
│   └── index_documents.py     # Indexation batch ChromaDB
├── ui/                        # Couche 5 — Interface (PySide6)
│   ├── __init__.py
│   ├── main_window.py         # Fenêtre principale
│   ├── chat_widget.py         # Widget chat streaming
│   ├── avatar_widget.py       # Avatar 2D QPainter
│   └── barre_orion.py         # Barre remplaçant taskbar
├── godot/                     # Couche 5 — Interface 3D (Godot)
│   ├── project.godot
│   ├── scenes/
│   ├── scripts/
│   └── assets/
├── voice/                     # Couche 4 — Voix
│   ├── __init__.py
│   ├── tts_engine.py          # Text-to-Speech (Piper/Kokoro)
│   └── stt_engine.py          # Speech-to-Text (Whisper)
├── automation/                # Couche 4 — Action OS
│   ├── __init__.py
│   └── os_controller.py       # Ouvrir apps, orga fichiers, etc.
├── finance/                   # Module Finance
│   ├── __init__.py
│   ├── csv_importer.py        # Import CSV/OFX/QIF
│   ├── categorizer.py         # Catégorisation auto LLM
│   └── dashboard.py           # Dashboard Wall Street
├── web/                       # Module Web
│   ├── __init__.py
│   └── scraper.py             # Scraping, recherche
├── vision/                    # Module Vision
│   ├── __init__.py
│   └── vlm_analyzer.py        # Analyse image VLM
├── security/                  # Sécurité
│   ├── __init__.py
│   ├── guardian.py            # Détection malware
│   └── privacy_shield.py      # Monitoring connexions
├── training/                  # Entraînement IA
│   └── train_lora.py          # Fine-tuning LoRA local
├── data/                      # Données persistantes
│   ├── conversations/         # Logs conversations (pour LoRA)
│   ├── documents/             # Documents pour RAG
│   ├── screenshots/           # Time Travel captures
│   ├── logs/                  # Logs daemon
│   ├── reports/               # Rapports matinaux
│   └── orion.db               # SQLite principal
├── tests/                     # Tests unitaires
│   ├── __init__.py
│   ├── test_screen_watcher.py
│   ├── test_system_watcher.py
│   ├── test_memory_palace.py
│   └── test_llm_manager.py
└── missions/                  # Missions structurées pour Claude
    ├── mission_01_screen_watcher.md
    ├── mission_02_system_watcher.md
    ├── mission_03_audio_watcher.md
    ├── mission_04_webcam_watcher.md
    ├── mission_05_input_watcher.md
    ├── mission_06_world_model.md
    ├── mission_07_memory_palace.md
    ├── mission_08_rag_engine.md
    ├── mission_09_tts_engine.md
    └── mission_10_stt_engine.md
```

## 🧠 Modèles LLM (Ollama)
| Rôle | Modèle | Taille VRAM | Usage |
|------|--------|-------------|-------|
| Principal | deepseek-coder:33b | ~20 Go | Raisonnement, code, chat |
| Vision | internvl2 / llava:13b | ~8 Go | Analyse écran temps réel |
| Rapide | qwen2.5:7b | ~5 Go | Réponses instantanées, routing |
| Créatif | mistral-nemo | ~7 Go | Brainstorming, storytelling |
| Memory | bge-m3 | ~2 Go | Embeddings RAG |
| TTS | kokoro / piper | ~1 Go | Voix locale |

## 🔄 Workflow Git
1. `just git-feature nom-du-module` → nouvelle branche
2. Code + tests
3. `just test` → vérifier que tout passe
4. `just lint` → formater le code
5. `just git-commit "feat: description claire"` → commit
6. `just git-push` → push
7. Merge sur main après validation

## 📝 Format des Commits
- `feat: ajout de fonctionnalité`
- `fix: correction de bug`
- `refactor: restructuration code`
- `test: ajout/modif tests`
- `docs: documentation`
- `chore: maintenance, dépendances`

## 🎯 Priorités de Développement
1. **S1** : Perception (screen, system, audio, webcam, input)
2. **S2** : Mémoire + World Model + RAG
3. **S3** : Interface Godot (avatar 3D)
4. **S4** : Voix (TTS continu + STT)
5. **S5** : Modes AURA + Barre Orion
6. **S6** : OS Controller + Automation
7. **S7** : Polish + Mobile Bridge
8. **S8** : Package + Release v1.0

## 💡 Notes pour Claude
- L'utilisateur est débutant mais très motivé (2-4h/jour)
- Privilégier la pédagogie et la compréhension
- Livrer rapidement une version utilisable, puis itérer
- Streaming par blocs de phrases (pas mot par mot)
- Architecture adaptative : PC maître, mobile client léger
- Expliquer CE que le code fait, pas juste le générer
# Addendum CLAUDE.md — Session du 30/07/2026

À coller à la fin du fichier `CLAUDE.md` existant, ou intégrer dans la section 6
("Instructions de travail pour Claude Code") comme nouveaux points.

---

## Renommage du projet : Orion → Luca's

Le projet s'appelle désormais **Luca's** (décidé par Cyril le 29-30/07/2026).
Le nom "OrionAI"/"Orion" reste utilisé dans le code et les chemins existants
jusqu'au renommage technique complet, prévu après stabilisation de S2.
Ne pas renommer partiellement (risque de casser des imports ou des chemins
de fichiers en plein travail) — le renommage se fera en un seul bloc, dédié.

## Leçons d'infrastructure (30/07/2026)

### Ollama : ne jamais avoir deux instances actives
L'application tray Ollama (icône barre des tâches) relance automatiquement
un serveur en tâche de fond. Si `ollama serve` est aussi lancé manuellement
en CLI, on se retrouve avec **deux process distincts** qui écoutent sur le
même port (11434), chacun avec son propre jeu de modèles chargés. Symptôme :
erreurs `404 model not found` sur un modèle qui apparaît pourtant dans
`ollama list`.

**Règle à suivre** : utiliser exclusivement `ollama serve` en CLI pendant le
développement. Ne pas relancer l'appli tray en parallèle. En cas de doute,
vérifier avec `tasklist | findstr ollama` — un seul `ollama.exe` doit
apparaître (l'appli tray `ollama app.exe` peut coexister mais ne doit pas
avoir relancé un `ollama.exe` enfant en double).

**À faire une fois pour toutes** : vérifier dans les paramètres de l'appli
Ollama si le démarrage automatique avec Windows est activé, et le désactiver
si c'est le cas, pour éviter que le doublon revienne à chaque redémarrage du PC.

### SQLite et FastAPI : attention aux threads
FastAPI traite chaque requête HTTP dans un thread du pool par défaut.
SQLite refuse par défaut d'être utilisé depuis un thread différent de celui
qui a ouvert la connexion (`check_same_thread=True` implicite). Solution
retenue dans `api/server.py` : instancier `OrionCore()` à chaque requête
plutôt qu'une seule fois au niveau du module — sans coût de logique, car
tout l'état de conversation vit dans le fichier SQLite, pas en mémoire Python.

### Toujours sauvegarder avant un nettoyage manuel de dossiers
Lors de l'audit Phase 0, les vrais dossiers `core/` et `ui/` ont été
supprimés par erreur en confondant avec les dossiers fantômes
`Fichier core/` et `Fichier ui/` (noms très proches, espace dans le nom).
Récupérés de justesse via un zip de sauvegarde antérieur trouvé sur le
bureau (`OrionProject/OrionAI.zip`).

**Règle à suivre** : avant toute suppression manuelle de fichiers/dossiers
dans le projet, faire un zip complet du dossier `C:\OrionAI` (ou son nom
futur) dans un emplacement séparé. Ne jamais supprimer un dossier dont le
nom ressemble à un autre sans vérifier d'abord ce qu'il contient
(`dir /S` ou ouverture manuelle).

### Un espace dans un nom de dossier = code Python mort garanti
Les dossiers `Fichier core/` et `Fichier ui/` contenaient du code
(notamment un fichier avec un import `pyqtSignal` de PyQt6 incompatible
avec PySide6), mais étaient **structurellement impossibles à importer**
en Python à cause de l'espace dans le nom. Un dossier avec un espace ne
peut jamais être un package Python valide (`from Fichier core import x`
est une erreur de syntaxe). Ce genre de nom est un signal fiable et
immédiat de fichier fantôme généré par un agent externe, sans même avoir
besoin de vérifier les imports ailleurs dans le code.
