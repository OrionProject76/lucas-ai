# 🌌 ORION AI — Kit d'Installation 24/7

Ce dossier contient tout ce qu'il faut pour transformer ton PC en **usine Orion** qui travaille jour et nuit.

---

## 📦 Contenu du Kit

| Fichier | Description |
|---------|-------------|
| `orion_daemon.py` | Cerveau nocturne — tourne 24/7 en arrière-plan |
| `justfile` | Commandes rapides (`just serve`, `just test`, etc.) |
| `CLAUDE.md` | Bible du projet — Claude Code lit ça automatiquement |
| `requirements_daemon.txt` | Dépendances Python du daemon |
| `missions/` | 10 missions structurées prêtes pour Claude Code |

---

## 🚀 Installation Étape par Étape

### Étape 1 : Installer `just` (task runner)

Dans PowerShell (admin) :
```powershell
winget install Casey.Just
```

Vérifie :
```powershell
just --version
```

### Étape 2 : Copier les fichiers dans OrionAI

Copie **tout le contenu** de ce dossier dans `C:\OrionAI\` :

```
C:\OrionAI\
├── orion_daemon.py          ← COPIER
├── justfile                 ← COPIER
├── CLAUDE.md                ← COPIER (remplace l'ancien si besoin)
├── requirements_daemon.txt  ← COPIER
├── missions/                ← COPIER (créer le dossier)
│   ├── mission_01_screen_watcher.md
│   ├── mission_02_system_watcher.md
│   ├── ...
│   └── mission_10_stt_engine.md
├── (tes fichiers existants)
```

### Étape 3 : Installer les dépendances du daemon

```powershell
cd C:\OrionAI
.\venv\Scripts\Activate.ps1
pip install -r requirements_daemon.txt
```

### Étape 4 : Tester le daemon

```powershell
# Mode visible (pour voir les logs en direct)
python orion_daemon.py

# Tu dois voir :
# 🌌 Orion Daemon initialisé.
# 📅 Planning configuré.
# 🚀 Orion Daemon démarré. Ctrl+C pour arrêter.
```

Appuie sur `Ctrl+C` pour arrêter.

### Étape 5 : Lancer le daemon en arrière-plan (24/7)

```powershell
# Mode invisible (Windows)
pythonw orion_daemon.py
```

Le daemon tourne maintenant en arrière-plan. Tu ne vois pas de fenêtre.

### Étape 6 : Vérifier que ça marche

```powershell
# Voir les logs en temps réel
just logs

# Ou directement :
Get-Content C:\OrionAI\data\logs\daemon.log -Tail 20 -Wait
```

Tu dois voir des lignes apparaître toutes les 30 secondes (screenshots).

### Étape 7 : Créer le service Windows (optionnel mais recommandé)

Pour que le daemon démarre automatiquement au boot :

1. Télécharge **NSSM** : https://nssm.cc/download
2. Extraire `nssm.exe` dans `C:\Windows\System32\`
3. Dans PowerShell admin :

```powershell
nssm install OrionDaemon
# Path : C:\OrionAI\venv\Scripts\pythonw.exe
# Arguments : C:\OrionAI\orion_daemon.py
# Démarrer le service
nssm start OrionDaemon
```

---

## 🎯 Utilisation Quotidienne

### Matin (08h)
```powershell
cd C:\OrionAI

# 1. Voir le rapport de la nuit
just report-today

# 2. Lancer Ollama + FastAPI
just all

# 3. Ouvrir VS Code + Cline (extension)
# 4. Ouvrir terminal + Claude Code
```

### Pendant la journée
```powershell
# Lancer une mission Claude Code
cd C:\OrionAI
claude
# Puis : "Implémente la mission missions/mission_01_screen_watcher.md"

# Ajustements rapides avec Cline (VS Code)
# → Ouvrir Cline dans la barre latérale
# → Sélectionner Ollama (qwen2.5:7b)
# → Demander des corrections

# Tests
just test

# Lint + format
just lint
```

### Soir (21h)
```powershell
# Commit + push
just git-commit "feat: module X terminé"
just git-push

# Le daemon continue de tourner la nuit
```

---

## 📋 Les 10 Missions — Ordre d'exécution

Donne ces missions à **Claude Code** une par une, dans cet ordre :

1. **`mission_01_screen_watcher.md`** — Capture écran + OCR
2. **`mission_02_system_watcher.md`** — Surveillance système Windows
3. **`mission_03_audio_watcher.md`** — Micro + STT Whisper
4. **`mission_04_webcam_watcher.md`** — Webcam + émotions
5. **`mission_05_input_watcher.md`** — Patterns clavier/souris
6. **`mission_06_world_model.md`** — Agrégation état temps réel
7. **`mission_07_memory_palace.md`** — Mémoire à 5 types
8. **`mission_08_rag_engine.md`** — Retrieval Augmented Generation
9. **`mission_09_tts_engine.md`** — Text-to-Speech
10. **`mission_10_stt_engine.md`** — Speech-to-Text

**Format pour Claude Code :**
```
Implémente la mission décrite dans missions/mission_01_screen_watcher.md
```

---

## 🔧 Commandes `just` Essentielles

| Commande | Action |
|----------|--------|
| `just all` | Lance Ollama + FastAPI + Daemon |
| `just serve` | Lance FastAPI seul |
| `just daemon` | Lance le daemon en arrière-plan |
| `just daemon-debug` | Lance le daemon en mode visible |
| `just test` | Exécute tous les tests |
| `just lint` | Formate le code avec ruff |
| `just check` | Lint + test + type check |
| `just train` | Entraînement LoRA manuel |
| `just index` | Indexation RAG manuelle |
| `just clean` | Cleanup manuel |
| `just report` | Génère le rapport matinal |
| `just logs` | Voir les logs en temps réel |
| `just doctor` | Vérifier l'environnement |

---

## 🛠️ Dépannage

### "ModuleNotFoundError" au lancement du daemon
```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements_daemon.txt
```

### "Permission denied" pour pynput (input watcher)
→ Lancer VS Code / terminal **en administrateur**

### Ollama ne répond pas
```powershell
ollama serve
# Dans un autre terminal :
ollama list
```

### Le daemon ne capture pas les screenshots
→ Vérifier que `pyautogui` est installé :
```powershell
python -c "import pyautogui; print('OK')"
```

---

## 📊 Rendement Attendu

| Période | Action | Résultat |
|---------|--------|----------|
| **Jour** | 4 missions Claude Code + ajustements Cline | 3-4 modules fonctionnels |
| **Nuit** | Daemon auto (LoRA, RAG, screenshots, cleanup) | Données prêtes le matin |
| **Semaine** | 20-28 modules | S1-S2 complètes |
| **8 semaines** | 60+ modules | v1.0 Orion fonctionnelle |

---

*"L'intelligence ne se contente pas de répondre. Elle anticipe, elle comprend, elle évolue."*

**Bienvenue dans l'usine Orion. 🌌**
