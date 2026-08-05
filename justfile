# justfile — Commandes Lucas AI
# Installation : winget install Casey.Just
# Usage : just <commande>

set shell := ["powershell.exe", "-c"]

# ─── LANCEMENT ───────────────────────────────────────────

# Lancer tout (Ollama + FastAPI + Daemon)
all:
    echo "🌌 Démarrage complet Luca's..."
    Start-Process powershell -ArgumentList "-c ollama serve" -WindowStyle Hidden
    Start-Sleep 2
    Start-Process powershell -ArgumentList "-c uvicorn api.server:app --reload --host 0.0.0.0 --port 8000 --ssl-certfile data/cert.pem --ssl-keyfile data/key.pem" -WindowStyle Hidden
    Start-Sleep 2
    pythonw lucas_daemon.py

# Lancer Ollama
ollama:
    ollama serve

# NB : l'app FastAPI est dans api/server.py, pas dans main.py — main.py est
# le point d'entrée PySide6 et expose une QApplication, pas une app ASGI.
#
# 0.0.0.0 + HTTPS, pas 127.0.0.1 : le pont mobile (PWA) en a besoin pour
# deux raisons distinctes — 0.0.0.0 pour être joignable depuis le
# téléphone sur le réseau local, HTTPS parce que getUserMedia() (micro,
# caméra) refuse de fonctionner hors d'un contexte sécurisé, et une IP
# réseau en HTTP n'en est pas un. API_TOKEN protège l'accès réseau
# depuis le 02/08/2026 — le commentaire qui justifiait 127.0.0.1 par
# « pas d'authentification » ne tenait plus.
#
# data/cert.pem et data/key.pem sont générés par mkcert (tools/mkcert.exe,
# jamais versionnés — voir .gitignore) pour localhost/127.0.0.1 et les IP
# réseau du PC. Si l'IP change (redémarrage, reconnexion Wi-Fi) et que le
# téléphone n'y accède plus, régénérer avec les nouvelles IP :
#   tools\mkcert.exe -cert-file data\cert.pem -key-file data\key.pem <IP...> localhost 127.0.0.1
#
# Tunnel Tailscale (Phase 4, tranché le 03/08/2026 — voir ROADMAP.md §2) :
# même commande `serve` ci-dessous une fois le certificat régénéré avec
# l'IP Tailscale (100.x.y.z) ou le nom MagicDNS en plus des IP existantes —
# `serve` écoute déjà sur 0.0.0.0, joignable via l'interface Tailscale sans
# changement de code. Deux étapes restent hors de portée d'un agent
# autonome (installation logicielle + connexion de compte) : installer le
# client Tailscale et exécuter `tailscale up` (authentification SSO) sur le
# PC ET le S25 Ultra. Une fois l'IP/nom obtenu après cette étape :
#   tools\mkcert.exe -cert-file data\cert.pem -key-file data\key.pem <IP Tailscale> <IP existantes...> localhost 127.0.0.1
# Et resserrer allow_origins dans api/server.py (actuellement "*", annoté
# dans le code comme provisoire) une fois cette origine connue.

# Lancer FastAPI (HTTPS, joignable depuis le téléphone)
serve:
    uvicorn api.server:app --reload --host 0.0.0.0 --port 8000 --ssl-certfile data/cert.pem --ssl-keyfile data/key.pem

# Lancer FastAPI en HTTP local seul — sans le pont mobile (micro/caméra
# indisponibles), pour un dépannage rapide sans certificat.
serve-http:
    uvicorn api.server:app --reload --host 127.0.0.1 --port 8000

# Lancer le daemon (arrière-plan Windows)
daemon:
    pythonw lucas_daemon.py

# Lancer le daemon en mode visible (debug)
daemon-debug:
    python lucas_daemon.py

# ─── DÉVELOPPEMENT ───────────────────────────────────────

# NB : les tests sont des test_*.py à la racine (pas de dossier tests/).
# Seul test_voice.py est exclu : ce n'est pas un test pytest mais un
# script de démo qui joue du son et appelle edge-tts en réseau.
# test_server.py était dans le même cas — il lançait uvicorn et bloquait
# la suite — il a été réécrit en vrais tests le 01/08/2026.

# Tests auto (avec coverage)
#
# ⚠️ NE JAMAIS remplacer `--cov=core` par `--cov=core.router` ou toute
# autre forme POINTÉE. Un nom de module fait importer ce module par
# coverage lui-même pour le résoudre en chemin — et ce second import de
# l'extension Rust de ChromaDB (PyO3) échoue avec « cannot load module
# more than once per process », ce qui fait tomber toute la collecte.
# La forme répertoire ne résout rien par import : elle marche.
# Trouvé le 05/08/2026 après avoir conclu à tort que la couverture
# n'était plus mesurable (ROADMAP.md §5.41).
#
# `security` ajouté le 05/08/2026 : il manquait à la commande standard,
# alors que c'est le code le plus sensible du projet — il n'était donc
# mesuré que par des campagnes ponctuelles.
test:
    pytest -v --ignore=test_voice.py --cov=core --cov=modules --cov=memory --cov=api --cov=security --cov-report=term-missing

# Tests rapides (sans coverage)
test-quick:
    pytest -v --ignore=test_voice.py

# NB : ceux-ci parlent aux VRAIS services — Ollama, Piper, registre
# Windows. Lents (~20 s) et dépendants de l'environnement, donc exclus
# de la suite par défaut via pytest.ini. Chaque test se saute proprement
# si sa dépendance manque, plutôt que d'échouer.

# Tests d'intégration (Ollama doit tourner)
test-integration:
    pytest test_integration.py -m integration -v

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

# ─── LUCA'S SPÉCIFIQUE ──────────────────────────────────

# Entraînement LoRA manuel
train:
    python training/train_lora.py --data data/conversations/

# Indexation RAG manuelle
index:
    python memory/index_documents.py

# Cleanup manuel
clean:
    python scripts/cleanup.py

# Oublier le dernier échange (question + réponse)
# À utiliser quand Luca's vient de répondre à côté : sans ça, elle voit sa
# propre mauvaise réponse juste au-dessus et la réimite. Mesuré sur la base
# réelle : 3/9 avec l'échange raté, 8/9 sans (voir config.py).
forget-last:
    python -c "from memory.memory_manager import MemoryManager; m=MemoryManager(); print(f'{m.forget_last_exchange()} message(s) oublié(s)')"

# Resynchroniser les copies de travail Cowork avec les vrais documents
#
# cowork_workspace/ contient des COPIES des 4 documents de référence, pour
# que l'outil Cowork y accède sans avoir de droits sur la racine du projet
# (permissions volontairement réduites). Elles divergent dès qu'un document
# racine est modifié — c'était le cas de 95 000 caractères sur ROADMAP.md
# au 05/08/2026.
#
# ⚠️ Sens unique, racine -> cowork, jamais l'inverse : la racine est la
# source de vérité. Une copie modifiée dans cowork_workspace sera écrasée,
# c'est voulu — l'alternative serait deux originaux, donc aucun.
#
# Non automatisé à chaque commit délibérément : un hook qui réécrit des
# fichiers pendant un commit laisse l'arbre de travail sale ou modifie
# silencieusement ce qui est validé. Une commande explicite est plus sûre
# qu'un automatisme surprenant — voir ROADMAP.md §5.37.
sync-docs:
    python -c "import shutil; [shutil.copy2(f, 'cowork_workspace/' + f) for f in ['ROADMAP.md', 'CLAUDE.md', 'IDEAS.md', 'VISION_LONG_TERME.md']]; print('4 documents resynchronises vers cowork_workspace/')"

# Rapport matinal manuel
report:
    python -c "from lucas_daemon import LucasDaemon; d=LucasDaemon(); d.generate_morning_report()"

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
