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

# ⚠️ Sans le pont mobile : micro et caméra sont indisponibles en HTTP.
#
# Dépannage local rapide, sans certificat
serve-http:
    uvicorn api.server:app --reload --host 127.0.0.1 --port 8000

# Régénérer le certificat HTTPS avec l'adresse Tailscale
#
# À lancer APRÈS `tailscale up` sur le PC, quand l'adresse 100.x.y.z est
# connue. Exemple :
#     just cert-tailscale 100.101.102.103
#
# ⚠️ Les IP existantes sont conservées volontairement. Sans elles, Luca
# deviendrait injoignable À LA MAISON en gagnant l'accès à distance —
# régression silencieuse, découverte le soir venu. Un certificat coûte la
# même chose avec trois adresses qu'avec une.
#
# Le certificat actuel couvre 192.168.1.12, 192.168.1.14, 127.0.0.1 et
# localhost. 192.168.1.14 est l'ancienne adresse du 05/08/2026, gardée
# tant que la réservation DHCP n'est pas confirmée — la retirer avant
# aurait rouvert la panne du matin même.
#
# Après régénération : le téléphone redemandera d'accepter le certificat
# (il a changé), une seule fois par adresse.
#
# Régénérer le certificat HTTPS avec l'adresse Tailscale (just cert-tailscale 100.x.y.z)
cert-tailscale ip:
    tools\mkcert.exe -cert-file data\cert.pem -key-file data\key.pem {{ip}} 192.168.1.12 192.168.1.14 127.0.0.1 localhost
    @echo "Certificat regenere. Relancer le serveur pour qu'il le charge :"
    @echo "  - tache planifiee LucasAPIServer, ou"
    @echo "  - just serve"

# Afficher ce que couvre le certificat actuel (diagnostic)
cert-info:
    python -c "import ssl; d = ssl._ssl._test_decode_cert(r'data/cert.pem'); print('Valide jusqu au', d.get('notAfter')); [print(' ', k, '=', v) for k, v in d.get('subjectAltName', ())]"

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
# ⚠️ `venv/Scripts/python.exe -m pytest`, PAS `pytest` nu — corrigé le
# 06/08/2026, et ce n'était pas cosmétique.
#
# `pytest` nu résolvait vers le Python GLOBAL
# (AppData/Local/Programs/Python/Python312), auquel il manque
# **20 paquets** présents dans le venv : ddgs, faster-whisper, pypdf,
# python-docx, pymupdf, ruff, mypy…
#
# Conséquence mesurée : `just test` collectait 1 249 tests avec 2 erreurs
# d'import (test_dependance_forme.py, test_modules.py — `ModuleNotFoundError:
# ddgs`), là où le venv en collecte 1 298 qui passent. Autrement dit, la
# commande officielle du projet testait un environnement qui n'est PAS
# celui dans lequel Luca's tourne — et deux fichiers de tests n'étaient
# jamais exécutés par elle.
test:
    venv/Scripts/python.exe -m pytest -v --ignore=test_voice.py --cov=core --cov=modules --cov=memory --cov=api --cov=security --cov=ui --cov-report=term-missing

# Tests rapides (sans coverage)
test-quick:
    venv/Scripts/python.exe -m pytest -v --ignore=test_voice.py

# NB : ceux-ci parlent aux VRAIS services — Ollama, Piper, registre
# Windows. Lents (~20 s) et dépendants de l'environnement, donc exclus
# de la suite par défaut via pytest.ini. Chaque test se saute proprement
# si sa dépendance manque, plutôt que d'échouer.

# Tests d'intégration (Ollama doit tourner)
test-integration:
    venv/Scripts/python.exe -m pytest test_integration.py -m integration -v

# ── Lint : TOUT le projet (élargi le 06/08/2026) ──────────────────────
#
# Couvrait auparavant core/ modules/ memory/ api/ ui/ test_router.py —
# soit un quart des alertes. Étaient hors périmètre : la racine (49
# fichiers de test, main.py, lucas_daemon.py, config.py), demos/, et
# surtout security/, le module où CLAUDE.md place le plus d'exigence.
#
# Ce n'est pas théorique : le bug du 06/08/2026 — le panneau de sécurité
# affichant « aucun signal » alors qu'il y en avait — vivait dans
# security/status.py, hors du périmètre linté (ROADMAP.md §5.59).
# ⚠️ `venv/Scripts/python.exe -m ruff` et non `ruff` tout court : ruff
# n'est PAS dans le PATH de cette machine, il vit dans le venv. La
# recette appelait `ruff` nu — elle échouait donc systématiquement en
# « terme non reconnu ». C'est ce qui explique que `ruff format`, qu'elle
# était censée lancer, n'ait jamais tourné (86 fichiers non formatés).
# Constaté en exécutant réellement `just lint` le 06/08/2026.
lint:
    venv/Scripts/python.exe -m ruff check .

# ⚠️ `ruff format` est SÉPARÉ de `lint` depuis le 06/08/2026, et c'est
# délibéré.
#
# Il était appelé par `lint`, mais n'avait manifestement jamais tourné :
# 29 fichiers du périmètre d'alors auraient été réécrits, 86 sur le
# projet entier. Un `just lint` qui réécrit 86 fichiers en passant rend
# toute relecture de diff impossible — on ne distingue plus un correctif
# d'un retour à la ligne.
#
# Et le résultat n'est pas neutre : le formateur éclate les listes
# compactes en une entrée par ligne. `KEYWORDS_SENSITIVE` de
# core/router.py (la liste qui décide ce qui ne sort JAMAIS de la
# machine) passerait de 5 lignes lisibles d'un coup d'œil à 17.
#
# Reformater reste possible, mais devient un acte explicite, à faire
# seul dans son propre commit :
format:
    venv/Scripts/python.exe -m ruff format .

# Voir ce que le formatage changerait, sans rien écrire.
format-check:
    venv/Scripts/python.exe -m ruff format --check .

# Type checking
# Meme motif que lint : mypy n'est pas dans le PATH non plus.
#
# `--check-untyped-defs` active le 06/08/2026 a la demande de Cyril. Sans
# lui, mypy IGNORE le corps de toute fonction sans annotations — soit une
# large part du projet, silencieusement non verifiee. Impact mesure avant
# activation : UNE seule erreur reelle (modules/piper_engine.py, un cache
# initialise a None dont le type se figeait a `None`), corrigee.
#
# `security/` ajoute au perimetre : mesure a 0 erreur sur 9 fichiers,
# donc gratuit — et c'est le module ou CLAUDE.md place le plus
# d'exigence. Meme correction de perimetre que pour `just lint`.
#
# PERIMETRE COMPLET depuis le 06/08/2026 : plus aucun angle mort. La
# racine (49 tests, main.py, lucas_daemon.py, config.py), demos/ et ui/
# etaient hors champ — 73 erreurs y dormaient, dont plusieurs vrais
# defauts de test. Detail du tri : ROADMAP.md §5.61.
#
# `ui/` a pu entrer parce que ses 12 alias Qt5 (Qt.AlignCenter,
# QPainter.Antialiasing...) ont ete migres vers la forme canonique
# PySide6 — verifie AVANT migration que les deux sont strictement egales
# au runtime, donc a comportement identique.
mypy:
    venv/Scripts/python.exe -m mypy . --ignore-missing-imports --check-untyped-defs --exclude '(^|/)(venv|Lucas3D)/'

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
    if (Test-Path training/train_lora.py) { python training/train_lora.py --data data/conversations/ } else { Write-Host "training/train_lora.py n'existe pas encore -- pas implémenté, voir README_INSTALL.md (tableau des commandes just cassées)." -ForegroundColor Yellow }

# Indexation RAG manuelle
index:
    python memory/index_documents.py

# Cleanup manuel
clean:
    if (Test-Path scripts/cleanup.py) { python scripts/cleanup.py } else { Write-Host "scripts/cleanup.py n'existe pas encore -- pas implémenté, voir README_INSTALL.md (tableau des commandes just cassées)." -ForegroundColor Yellow }

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
