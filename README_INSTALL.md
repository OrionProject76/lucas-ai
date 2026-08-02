# 🌌 LUCA'S — Installation

Ce document couvre l'installation complète : l'application principale
(interface + API) et, en option, le daemon 24/7.

> Le projet s'appelle désormais **Luca's**. Le renommage technique du code
> (classes, fichiers, dossier `Orion3D/`, base de données) est fait le
> 02/08/2026 — voir `ROADMAP.md` section 6. Restent volontairement différés,
> pour ne pas casser un environnement déjà installé sans supervision directe :
> le dossier racine `C:\OrionAI` et l'organisation GitHub `OrionProject76`.
> Les chemins ci-dessous restent donc en `OrionAI` pour ces deux éléments
> seulement.

---

## 📦 Ce que contient le dépôt

| Élément | Rôle |
|---|---|
| `main.py` | Point d'entrée de l'interface PySide6 |
| `api/server.py` | API FastAPI (REST + WebSocket) — mobile et Godot |
| `core/` | Cerveau de Luca's : routage local/cloud, mémoire, World Model |
| `modules/` | RAG, vision, voix, web, finance |
| `lucas_daemon.py` | Daemon 24/7 optionnel (tâches de fond) |
| `Lucas3D/` | Frontend Godot 4 (avatar holographique) |
| `missions/` | 10 fiches de spécification pour Claude Code |
| `justfile` | Raccourcis de commandes |

---

## 🚀 Installation

### Prérequis

- **Python 3.12** (le projet tourne sur 3.12.7)
- **Ollama** installé et fonctionnel — [ollama.com](https://ollama.com)
- **git**

`just` est optionnel (raccourcis de commandes) :

```powershell
winget install Casey.Just
```

### Étape 1 : Récupérer le dépôt

```powershell
git clone https://github.com/OrionProject76/lucas-ai.git C:\OrionAI
cd C:\OrionAI
```

### Étape 2 : Créer l'environnement virtuel

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

### Étape 3 : Installer les dépendances

```powershell
pip install -r requirements.txt
```

Environ 99 paquets, ~1,1 Go. C'est tout ce qu'il faut pour l'interface et
l'API.

Le daemon 24/7 a ses propres dépendances (`requirements_daemon.txt`) —
voir la section dédiée plus bas. **Ne l'installe pas maintenant** : plusieurs
de ses paquets exigent une compilation C sous Windows et ne servent qu'aux
modules de perception, pas encore écrits.

### Étape 4 : Configurer les secrets

```powershell
copy .env.example .env
```

Le `.env` n'est jamais versionné. La seule variable actuelle,
`OPENAI_API_KEY`, est **optionnelle** : laissée vide, Luca's reste en 100 %
local via Ollama. Voir `CLAUDE.md` règle 3 pour l'architecture hybride.

### Étape 5 : Préparer Ollama

```powershell
ollama serve
```

Dans un autre terminal, récupérer le modèle utilisé par défaut
(`MODEL_NAME` dans `config.py`) :

```powershell
ollama pull qwen2.5
ollama list
```

> ⚠️ **Ne jamais avoir deux instances d'Ollama actives.** L'appli tray relance
> un serveur en tâche de fond ; combinée à un `ollama serve` en CLI, on obtient
> deux process sur le port 11434 avec des jeux de modèles différents, et des
> erreurs `404 model not found` sur un modèle pourtant listé. Vérifier avec
> `tasklist | findstr ollama`. Détails dans `CLAUDE.md`.

---

## ▶️ Lancer Luca's

Avec le venv activé et Ollama démarré :

```powershell
# Interface principale (PySide6)
python main.py

# API seule (mobile, Godot)
uvicorn api.server:app --reload --host 127.0.0.1 --port 8000
```

L'API expose `GET /status`, `GET /system`, `POST /chat` et `WS /ws`.

> ⚠️ Elle écoute sur `127.0.0.1` : joignable depuis ce PC uniquement.
> Elle n'a aucune authentification et `GET /history` renvoie toutes les
> conversations — l'ouvrir au réseau (`0.0.0.0`) la rendrait lisible par
> n'importe quel appareil du WiFi. Le passage au réseau viendra en Phase 5
> avec le mobile, et exigera un jeton partagé au préalable.

### Vérifier que tout fonctionne

```powershell
just test-quick                   # suite complète, ~3 s, tout mocké
just test-integration             # chaîne réelle avec Ollama, ~20 s
python -c "import config, core.lucas_core, main; print('imports OK')"
```

Les tests d'intégration parlent aux vrais services — Ollama, Piper, le
registre Windows. Ils sont exclus de la suite par défaut parce qu'ils
sont lents et dépendent de l'environnement. Chacun se saute proprement
si sa dépendance manque : un test rouge parce qu'Ollama est éteint
n'apprendrait rien.

---

## 🌙 Daemon 24/7 (optionnel)

Le daemon tourne en arrière-plan pour les tâches de fond (captures d'écran,
rapports). Il n'est pas nécessaire pour utiliser Luca's.

```powershell
pip install -r requirements_daemon.txt
python lucas_daemon.py            # mode visible, pour voir les logs
pythonw lucas_daemon.py           # mode invisible, arrière-plan
```

> `requirements_daemon.txt` déclare aujourd'hui plus que ce que le code
> importe (`pyaudio`, `webrtcvad`, `openai-whisper`, `piper-tts`,
> `sentence-transformers`, `pynput`, `pywinauto`, `sounddevice`). Ces paquets
> correspondent aux missions 03-05 et 09-10, pas encore implémentées, et
> certains échouent à l'installation sous Windows faute de compilateur C.
> Le daemon actuel n'a besoin que de `Pillow`, `opencv-python`, `numpy`,
> `pyautogui`, `schedule`, `psutil` et `pywin32`.

Suivre les logs :

```powershell
Get-Content C:\OrionAI\data\logs\daemon.log -Tail 20 -Wait
```

### Démarrage automatique au boot (optionnel)

1. Télécharger **NSSM** : https://nssm.cc/download
2. Extraire `nssm.exe` dans `C:\Windows\System32\`
3. En PowerShell admin :

```powershell
nssm install LucasDaemon
# Path      : C:\OrionAI\venv\Scripts\pythonw.exe
# Arguments : C:\OrionAI\lucas_daemon.py
nssm start LucasDaemon
```

---

## 🔧 Commandes `just`

**Fonctionnelles aujourd'hui :**

| Commande | Action |
|---|---|
| `just ollama` | Lance `ollama serve` |
| `just daemon` | Lance le daemon en arrière-plan |
| `just daemon-debug` | Lance le daemon en mode visible |
| `just logs` | Suit les logs du daemon |
| `just install` | Installe les deux fichiers de dépendances |
| `just doctor` | Affiche les versions Python / Ollama / uvicorn |
| `just serve` | Lance l'API sur `127.0.0.1:8000` |
| `just all` | Ollama + API + daemon |
| `just test` | Tous les tests avec coverage |
| `just test-quick` | Tous les tests, sans coverage |
| `just lint` | `ruff check` puis `ruff format` (réécrit les fichiers) |
| `just mypy` | Vérification de types |
| `just git-commit "msg"` | `git add .` puis commit |
| `just git-push` | Push sur `main` |
| `just git-feature nom` | Crée la branche `feature/nom` |

**⚠️ Encore cassées — leur cible n'existe pas :**

| Commande | Problème |
|---|---|
| `just index` | `memory/index_documents.py` absent |
| `just clean` | `scripts/cleanup.py` absent |
| `just train` | `training/train_lora.py` absent |

Ces trois-là décrivent l'arborescence visée dans `CLAUDE.md`, pas celle
d'aujourd'hui. Elles fonctionneront quand les modules correspondants
seront écrits.

---

## 🛠️ Dépannage

### `ModuleNotFoundError` au lancement

Vérifier que le venv est bien activé :

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Ollama ne répond pas

```powershell
tasklist | findstr ollama     # un seul ollama.exe attendu
ollama serve
ollama list
```

### `404 model not found` alors que le modèle est listé

Symptôme typique du doublon d'instances Ollama — voir l'avertissement de
l'étape 5.

### L'interface se lance mais le chat ne répond pas

Ollama doit tourner **avant** `main.py`. Vérifier `OLLAMA_URL` et
`MODEL_NAME` dans `config.py`.

---

## 📋 Les 10 missions

Fiches de spécification à donner à Claude Code, dans l'ordre :

1. `mission_01_screen_watcher.md` — Capture écran + OCR
2. `mission_02_system_watcher.md` — Surveillance système Windows
3. `mission_03_audio_watcher.md` — Micro + STT Whisper
4. `mission_04_webcam_watcher.md` — Webcam + émotions
5. `mission_05_input_watcher.md` — Patterns clavier/souris
6. `mission_06_world_model.md` — Agrégation état temps réel
7. `mission_07_memory_palace.md` — Mémoire à 5 types
8. `mission_08_rag_engine.md` — Retrieval Augmented Generation
9. `mission_09_tts_engine.md` — Text-to-Speech
10. `mission_10_stt_engine.md` — Speech-to-Text

```
Implémente la mission décrite dans missions/mission_01_screen_watcher.md
```

---

*"L'intelligence ne se contente pas de répondre. Elle anticipe, elle comprend, elle évolue."*
