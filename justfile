# justfile — Commandes Orion AI
# Installation : winget install Casey.Just
# Usage : just <commande>

set shell := ["powershell.exe", "-c"]

# ─── LANCEMENT ───────────────────────────────────────────

# Lancer tout (Ollama + FastAPI + Daemon)
all:
    echo "🌌 Démarrage complet Orion..."
    Start-Process powershell -ArgumentList "-c ollama serve" -WindowStyle Hidden
    Start-Sleep 2
    Start-Process powershell -ArgumentList "-c uvicorn api.server:app --reload --host 127.0.0.1 --port 8000" -WindowStyle Hidden
    Start-Sleep 2
    pythonw orion_daemon.py

# Lancer Ollama
ollama:
    ollama serve

# NB : l'app FastAPI est dans api/server.py, pas dans main.py — main.py est
# le point d'entrée PySide6 et expose une QApplication, pas une app ASGI.
# 127.0.0.1 et non 0.0.0.0 : l'API n'a pas d'authentification, elle ne doit
# pas être joignable depuis le réseau local. À revoir en Phase 5 (mobile).

# Lancer FastAPI
serve:
    uvicorn api.server:app --reload --host 127.0.0.1 --port 8000

# Lancer le daemon (arrière-plan Windows)
daemon:
    pythonw orion_daemon.py

# Lancer le daemon en mode visible (debug)
daemon-debug:
    python orion_daemon.py

# ─── DÉVELOPPEMENT ───────────────────────────────────────

# NB : les tests sont des test_*.py à la racine (pas de dossier tests/).
# Seul test_voice.py est exclu : ce n'est pas un test pytest mais un
# script de démo qui joue du son et appelle edge-tts en réseau.
# test_server.py était dans le même cas — il lançait uvicorn et bloquait
# la suite — il a été réécrit en vrais tests le 01/08/2026.

# Tests auto (avec coverage)
test:
    pytest -v --ignore=test_voice.py --cov=core --cov=modules --cov=memory --cov=api --cov-report=term-missing

# Tests rapides (sans coverage)
test-quick:
    pytest -v --ignore=test_voice.py

# NB : ruff format réécrit les fichiers sur place.

# Linting + formatage
lint:
    ruff check core/ modules/ memory/ api/ ui/ test_router.py
    ruff format core/ modules/ memory/ api/ ui/ test_router.py

# Type checking
mypy:
    mypy core/ modules/ memory/ api/ --ignore-missing-imports

# Vérification complète (lint + test + type)
check: lint test mypy

# ─── GIT ─────────────────────────────────────────────────

# Commit rapide avec message
git-commit msg:
    git add .
    git commit -m "{{msg}}"

# Push
git-push:
    git push origin main

# Nouvelle branche feature
git-feature name:
    git checkout -b feature/{{name}}

# ─── ORION SPÉCIFIQUE ────────────────────────────────────

# Entraînement LoRA manuel
train:
    python training/train_lora.py --data data/conversations/

# Indexation RAG manuelle
index:
    python memory/index_documents.py

# Cleanup manuel
clean:
    python scripts/cleanup.py

# Rapport matinal manuel
report:
    python -c "from orion_daemon import OrionDaemon; d=OrionDaemon(); d.generate_morning_report()"

# Voir les logs du daemon
logs:
    Get-Content data/logs/daemon.log -Tail 50 -Wait

# Voir le rapport du jour
report-today:
    Get-Content data/reports/report_(Get-Date -Format yyyyMMdd).txt

# ─── INSTALLATION ────────────────────────────────────────

# Installer les dépendances
install:
    pip install -r requirements.txt
    pip install -r requirements_daemon.txt

# Vérifier l'environnement
doctor:
    python --version
    ollama --version
    uvicorn --version
    echo "✅ Environnement OK"
