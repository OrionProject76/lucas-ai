# LUCA'S — Contexte Projet pour Claude Code

## 🎯 Vision
Luca's est un système d'exploitation cognitif — une couche d'intelligence vivante entre l'utilisateur et Windows 11. Windows devient invisible ; Luca's devient l'interface.

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
3. **Local par défaut, cloud en exception** — Ollama traite tout, sauf les questions complexes explicitement routées ; JAMAIS de donnée sensible vers le cloud
4. **CSV uniquement** pour la finance — PAS de connexions bancaires directes
5. **Tout en anglais** : variables, fonctions, comments, docstrings
6. **Type hints obligatoires** sur toutes les fonctions
7. **Docstrings** pour chaque classe et fonction publique
8. **Tests unitaires** pour chaque module avec pytest
9. **Git commit** à chaque feature terminée avec message clair
10. **PAS d'avatar 3D Unity/Unreal** — Godot 4 seul
11. **PAS de voice cloning avancé/XTTS** — Piper/Kokoro seuls
12. **PAS de Swarm Intelligence** en v1.0 (plusieurs LLM autonomes coordonnés — `IDEAS.md` #38) — reporté v1.1+

### ⚠️ Précision sur la règle 3 — architecture hybride (assouplie le 01/08/2026)

La règle 3 disait « Ollama local uniquement — PAS d'API cloud ». Elle contredisait
le code, qui route déjà vers le cloud (`core/router.py`, `core/cloud_llm.py`).
Cyril valide explicitement l'architecture hybride : c'est la règle qui change,
pas le code qui disparaît.

**Le principe** : le local est le défaut, le cloud est l'exception justifiée par
la qualité de réponse — jamais par confort. Et une donnée sensible ne sort
jamais, quelle que soit la question posée.

| Destination | Quand | Mots-clés déclencheurs |
|---|---|---|
| **Cloud** | Questions complexes où la qualité de réponse compte | `analyse`, `compare`, `projection`, `stratégie`, `optimise`, `20 ans` |
| **Local (forcé)** | Finance perso, documents privés, identité — **même si un mot-clé cloud est présent** | `portfolio`, `risque`, `budget`, `dépense`, `salaire`, `revenu`, `compte bancaire`, `impôt`, `iban`, `mot de passe`… |
| **Local (forcé)** | Questions sur les documents personnels (RAG) | voir `KEYWORDS_RAG` |
| **Local** | Tout le reste (défaut sûr) | — |

**Le local gagne toujours en cas de conflit.** « Analyse mon portfolio » contient
`analyse` (cloud) et `portfolio` (sensible) → reste local. Cette priorité est
non négociable : c'est elle qui rend l'assouplissement acceptable.

**Ce qui est joint à une requête cloud** est volontairement réduit :
- pas de contexte RAG (extraits de documents personnels)
- pas d'événements système : la table `system_events` contient des extraits
  de contenu sensible (voir `voice_manager._log`), elle ne sort jamais
- **pas le titre de la fenêtre active** : « releve_bancaire.pdf » révèle sur
  quoi Cyril travaille même quand la question est anodine. CPU et RAM
  restent joints, ils ne disent rien de lui
- historique tronqué à `CLOUD_HISTORY_MESSAGES` (6) au lieu de 100 en local

**Implémentation de référence** : `core/router.py` — `route()`, `is_sensitive()`,
`should_use_rag()`. Toute évolution du routage passe par ce fichier, jamais par
un appel cloud direct ailleurs dans le code. Tests : `test_router.py`.

Cohérent avec `VISION_LONG_TERME.md` §4 : « la sécurité vient du contrôle de
*ce qui* est envoyé et *quand*, pas du canal utilisé ».

#### La même règle s'applique à la voix (TTS) — ajouté le 01/08/2026

Le TTS est une seconde surface de sortie : `edge_tts` envoie à Microsoft le
texte à prononcer. Deux moteurs, un routeur, même principe que pour le LLM.

| Moteur | Quand | Où va le texte |
|---|---|---|
| **edge_tts** (défaut) | Contenu sans marqueur sensible | Serveurs Microsoft |
| **Piper** (forcé) | Contenu sensible ou question RAG | Reste sur la machine |

⚠️ **Le défaut est inversé par rapport au routage LLM** : ici le cloud est le
défaut, parce que la voix edge est nettement meilleure et que le TTS ne
transmet que du texte déjà affiché à l'écran. Ce n'est pas un oubli.

**Le routeur analyse la question ET la réponse.** « Quel est mon salaire ? » →
« Il est de 3200 euros » : la réponse seule ne contient aucun mot-clé sensible
et serait partie chez Microsoft. Implémentation : `route_voice()` dans
`core/router.py`, qui réutilise `is_sensitive()` et `should_use_rag()`.

**Si Piper est indisponible** (modèle `.onnx` absent, erreur de chargement) sur
un contenu sensible : **rien n'est prononcé**. Le texte reste lisible à
l'écran, un message le signale dans le chat, et l'événement
`tts_skipped_sensitive` est enregistré en base. Jamais de repli vers le cloud
par défaut.

**Interrupteur `TTS_ALLOW_CLOUD_ON_SENSITIVE`** (`config.py`, défaut `False`) :
à `True`, ce cas précis bascule sur edge_tts — donc **du texte sensible part
chez Microsoft**. C'est une dérogation consciente, à activer par Cyril seul,
tracée par l'événement `tts_cloud_on_sensitive`. Elle deviendra une boîte de
dialogue de confirmation lors du chantier UI.

Les extraits enregistrés en base sont tronqués à 80 caractères : la table
d'événements ne doit pas devenir une copie du contenu qu'on refuse d'envoyer.

Tests : `test_voice_router.py`.

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

## 🚀 Autonomie d'exécution (acté le 01/08/2026)

Cyril fait confiance au jugement technique de Claude Code. À partir de maintenant, avance en autonomie sur :
- L'implémentation de ce qui est déjà planifié dans ROADMAP.md et validé dans un plan approuvé
- Les tests, corrections de bugs, refactoring qui ne changent pas le comportement observable
- Les commits et push — commite et pousse automatiquement après chaque étape testée et fonctionnelle, sans demander "je pousse ?" à chaque fois
- Les choix d'implémentation mineurs (nommage, structure de fichier, détails qui n'engagent pas Cyril)
- La revue de code de l'existant, la détection d'incohérences entre la doc et le code

Reviens systématiquement vers Cyril AVANT d'agir, même en autonomie, uniquement dans ces cas :
1. Sécurité : tout ce qui touche à un accès réseau externe, l'envoi de données hors de la machine, ou une donnée sensible (finance, documents personnels, identité)
2. Contradiction avec une règle de CLAUDE.md ou VISION_LONG_TERME.md — la règle ne se modifie jamais silencieusement
3. Choix d'architecture engageant plusieurs semaines de travail ou difficile à défaire (ex : changement de moteur de rendu, de framework, de modèle LLM principal)
4. Ambiguïté réelle entre plusieurs options qui changent le résultat final pour Cyril, sans réponse évidente

Dans ces 4 cas : présenter un plan clair (comme pour la règle 3 et le TTS), attendre validation explicite avant d'exécuter. Dans tous les autres cas : avancer, tester, committer, pousser, puis résumer ce qui a été fait — sans attendre de permission à chaque étape.

### Précision : l'expérience utilisateur relève de l'autonomie normale (acté le 01/08/2026)

Toute amélioration d'expérience — fluidité, animations, transitions, messages plus clairs, cohérence visuelle, micro-interactions — fait partie du périmètre d'autonomie ordinaire. Pas de validation à demander pour ce type de détail.

Cette précision ne retire rien aux 4 cas ci-dessus. Le confort et la fluidité n'en font simplement pas partie : ils ne touchent ni à la sécurité, ni à une règle, ni à l'architecture, et ne constituent pas une ambiguïté au sens du cas 4.

Reste à distinguer : un changement **esthétique de fond** — remplacer le visage de l'avatar par une forme abstraite, changer la charte de couleurs — engage l'identité du produit et se discute. Adoucir une transition, corriger un tremblement, rendre un message d'attente compréhensible : non, c'est du travail normal.

## 🛡️ Liberté conditionnée à la protection (acté le 01/08/2026)

⚠️ **Ne pas confondre avec la section précédente.** « Autonomie d'exécution »
concerne Claude Code au travail sur le projet. Cette section-ci concerne
**Luca's elle-même** : le périmètre d'action que le produit fini aura sur la
machine de Cyril.

> La liberté d'action de Luca's est conditionnée à sa capacité de protection.

Luca's doit savoir reconnaître et bloquer les actions suspectes venant du
réseau **avant** d'obtenir des libertés d'action plus étendues. La confiance
est réciproque : elle implique une responsabilité de protection mutuelle, pas
un accès sans discernement.

**Règle opposable** : les modules `security/guardian.py` et
`security/privacy_shield.py` sont une **dépendance directe de toute extension
future des libertés d'action de Luca's**. Toute proposition d'élargir son
autonomie (actions système, accès réseau, exécution automatique) se répond
d'abord par « où en sont Guardian et Privacy Shield, et sont-ils testés ? ».

Ce principe **n'assouplit rien aujourd'hui** : liste blanche, confirmations et
règle 3 restent en vigueur à l'identique. Il pose la condition qui permettrait
un jour de les assouplir en connaissance de cause.

Doctrine complète : `VISION_LONG_TERME.md` §4.1.

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
│   └── barre_orion.py         # Barre Luca's remplaçant la taskbar
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
5. **S5** : Modes AURA + Barre Luca's
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
