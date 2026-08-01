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
    Start-Process powershell -ArgumentList "-c uvicorn api.server:app --reload --host 0.0.0.0 --port 8000" -WindowStyle Hidden
    Start-Sleep 2
    pythonw orion_daemon.py

# Lancer Ollama
ollama:
    ollama serve

# NB : l'app FastAPI est dans api/server.py, pas dans main.py — main.py est
# le point d'entrée PySide6 et expose une QApplication, pas une app ASGI.

# Lancer FastAPI
serve:
    uvicorn api.server:app --reload --host 0.0.0.0 --port 8000

# Lancer le daemon (arrière-plan Windows)
daemon:
    pythonw orion_daemon.py

# Lancer le daemon en mode visible (debug)
daemon-debug:
    python orion_daemon.py

# ─── DÉVELOPPEMENT ───────────────────────────────────────

# NB : les tests sont des test_*.py à la racine (pas de dossier tests/).
# test_server.py et test_voice.py sont exclus : ce ne sont pas des tests
# pytest mais des scripts de démo — test_server lance uvicorn et bloque
# indéfiniment, test_voice joue du son et appelle edge-tts en réseau.

# Tests auto (avec coverage)
test:
    pytest -v --ignore=test_server.py --ignore=test_voice.py --cov=core --cov=modules --cov=memory --cov=api --cov-report=term-missing

# Tests rapides (sans coverage)
test-quick:
    pytest -v --ignore=test_server.py --ignore=test_voice.py

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
