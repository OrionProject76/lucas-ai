# config.py — tous les réglages de Luca's au même endroit

import os
from pathlib import Path

# Charge le fichier .env s'il existe (secrets locaux, jamais versionnés).
# python-dotenv est optionnel : sans lui, les variables d'environnement
# système restent lues normalement et l'app démarre quand même.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

# --- IA locale (Ollama) ---
# ⚠️ 127.0.0.1 et JAMAIS « localhost ». Mesuré sur cette machine :
#     localhost  → 2,26 s / 2,39 s / 2,19 s
#     127.0.0.1  → 0,14 s / 0,14 s / 0,14 s
# Le modèle ne travaille que ~130 ms (load 96 + prompt 12 + génération 25,
# d'après les compteurs d'Ollama). Les 2,05 s restantes sont un timeout de
# résolution : Windows résout « localhost » en IPv6 (::1) d'abord, Ollama
# n'écoute qu'en IPv4, et chaque appel attend l'échec avant de basculer.
# Ce surcoût était payé par CHAQUE requête — chat, vision, embeddings.
OLLAMA_HOST = "http://127.0.0.1:11434"
OLLAMA_URL = f"{OLLAMA_HOST}/api/chat"
# ⚠️ Tag explicite obligatoire. « qwen2.5 » sans tag ne correspond à
# aucun modèle exactement : Ollama devine « qwen2.5:latest », et cette
# résolution échoue tant que son registre n'est pas chargé — c'était la
# cause des « 404 model not found » intermittents au démarrage.
# qwen2.5:7b et qwen2.5:latest ont le même digest : même modèle, celui
# que ROADMAP.md donne comme validé en usage réel.
MODEL_NAME = "qwen2.5:7b"

# Liste des modèles disponibles (pour futur sélecteur)
AVAILABLE_MODELS = ["qwen2.5", "llama3.2", "mistral", "codellama"]

# --- Timeouts ---
OLLAMA_CONNECT_TIMEOUT = 10   # secondes pour se connecter à Ollama
OLLAMA_READ_TIMEOUT = 120     # secondes pour recevoir la réponse

# --- IA cloud (optionnel, désactivé pour l'instant) ---
# Jamais de clé en dur ici : ce fichier est suivi par git.
# La valeur vient de .env (ignoré par git) ou des variables d'environnement.
# Voir .env.example pour le modèle. Chaîne vide = cloud désactivé.
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# --- Voix (TTS) ---
# Deux moteurs, un routeur : core.router.route_voice() décide.
# Choix de Cyril, 01/08/2026, après écoute comparée (demos/demo_voices.py).
EDGE_TTS_VOICE = "fr-FR-HenriNeural"   # voix cloud Microsoft (défaut)
PIPER_VOICE = "fr_FR-siwis-medium"     # voix locale retenue
PIPER_VOICES_DIR = "data/voices"       # modèles .onnx (non versionnés)

# Alternatives retenues, à basculer sans rien retélécharger :
#   EDGE_TTS_VOICE = "fr-FR-DeniseNeural"   (féminine, cloud)
#   PIPER_VOICE    = "fr_FR-upmc-medium"    (masculine, locale)
#
# ⚠️ Les deux voix Piper ne se ressemblent pas : siwis est féminine,
# Henri (edge) est masculine. Le moteur change selon la sensibilité du
# contenu (route_voice), donc la voix change aussi en cours d'usage.
# C'est audible et volontaire — la bascule vers le local s'entend, ce qui
# est plutôt une bonne chose. Pour une voix constante, prendre upmc.

# ⚠️ SÉCURITÉ — laisser à False sauf décision consciente.
# À True, si Piper est indisponible (modèle manquant, erreur de chargement),
# un texte SENSIBLE est prononcé par edge_tts, donc envoyé à Microsoft.
# À False, ce texte n'est simplement pas prononcé et l'événement est loggué.
# Voir CLAUDE.md règle 3, section TTS.
TTS_ALLOW_CLOUD_ON_SENSITIVE: bool = False

# --- Vision : analyse de l'écran (VLM) ---
# Modèle vision local, servi par Ollama. « llava » est installé sur cette
# machine ; internvl2 est envisagé en v1.1 (voir CLAUDE.md, tableau LLM).
VLM_MODEL = "llava"

# ── Le VLM est DÉSACTIVÉ en v1.0 — décision de Cyril, 01/08/2026 ──────
#
# ⚠️ Ce n'est PAS un abandon de la description visuelle. C'est une
# suspension le temps de changer de modèle. Voir le compromis assumé
# plus bas : il faut le connaître avant de toucher à ce réglage.
#
# MOTIF — llava ne se trompe pas, il FABRIQUE. Observé en conditions
# réelles, quatre fois sur quatre captures :
#   • « Error: unable to connect to local socket path /var/run/docker.sock »
#   • « mount: mounting /dev/sda6 on /media failed: Invalid argument »
#   • « Je ne peux pas aider avec la description de l'image »
#   • un traceback Python complet — « TypeError: 'int' object is not
#     iterable », fichier et numéro de ligne inclus — suivi de trois
#     paragraphes de solution pour un bug inexistant
# Aucune de ces phrases n'était à l'écran. Sur les trois essais réels
# finaux, sa contribution a dégradé deux réponses et n'en a amélioré
# aucune ; le faux traceback contaminait jusqu'à la réponse voisine.
#
# Une vision absente se voit. Une vision fausse se croit. C'est ce qui
# rend llava plus nuisible qu'utile ici, malgré l'étiquette « indicatif,
# peut se tromper » de _compose_vision_block().
#
# ⚠️ CE QU'ON PERD, ET IL FAUT L'ASSUMER : Luca's ne sait plus dire
# QUELLE APPLICATION est ouverte ni comment l'écran est disposé. Elle lit
# le texte, elle ne décrit plus la scène. Sur un écran sans texte — une
# image, une vidéo, un graphique — elle n'a plus rien à dire. Ce n'est
# pas un détail : c'est la moitié de la promesse de la couche perception
# (VISION_LONG_TERME.md §2), mise en pause faute d'un modèle fiable.
#
# ➜ v1.1 : reprendre la description visuelle avec internvl2, déjà prévu
#   au tableau des modèles de CLAUDE.md. Le point de vigilance reste la
#   contention GPU avec Ollama (VISION_LONG_TERME.md §3) — c'est
#   précisément ce qui avait fait préférer llava. Remettre
#   VLM_ENABLED = True et VLM_MODEL = "internvl2" suffit à réactiver le
#   chemin : le code des deux sources est conservé intact, rien n'a été
#   supprimé.
VLM_ENABLED: bool = False
#
# ⚠️ LIMITE CONNUE — qwen2.5 dérive en chinois sur contexte long. Observé
# une fois, avec un bloc vision de 12 447 caractères et 91 messages
# d'historique. Non reproduit depuis que les deux sont bornés
# (VLM_MAX_CHARS, VISION_HISTORY_MESSAGES). Comportement du modèle, pas
# bug applicatif : à ne pas poursuivre indéfiniment.

# ⚠️ Une capture d'écran peut contenir un relevé bancaire ou un mot de
# passe affiché. Elle ne quitte jamais la machine (Ollama local), et une
# question qui déclenche la vision est forcée en LOCAL par route() :
# sinon la description de l'écran partirait au cloud même si l'image
# reste ici. Voir CLAUDE.md règle 3.
VISION_ENABLED: bool = True

# ── OCR : lecture du texte affiché ────────────────────────────────────
# llava ne sait pas lire un écran (redimensionnement interne vers ~336 px,
# le texte devient illisible). L'OCR extrait le texte exact en CPU, le VLM
# garde le contexte visuel. Voir modules/ocr_engine.py.
OCR_ENABLED: bool = True

# Un écran 4K peut produire plusieurs milliers de caractères. Sans borne,
# le texte de l'écran noierait le reste du prompt — historique, événements,
# prompt système.
OCR_MAX_CHARS: int = 2000

OCR_LANGUAGES = ["fr", "en"]

# ⚠️ Le VLM n'était borné par RIEN, alors que l'OCR l'était. Mesuré en
# usage réel sur « c'est écrit quoi ? » : llava a rendu 10 270 caractères
# de description, pour 1 761 caractères de texte réellement lu. Le bloc
# vision pesait 12 447 caractères — du bavardage qui noie l'observation
# utile et pousse qwen2.5 hors de sa fenêtre confortable.
# Le contexte visuel sert à SITUER (quelle application, quelle
# disposition) ; c'est l'OCR qui porte le contenu.
VLM_MAX_CHARS: int = 1200

# --- Voix : transcription (STT) ---
# « base » ≈ 150 Mo, suffisant pour la v1.0 ; « small » ≈ 500 Mo, plus
# précis, envisagé en v1.1 (mission_10_stt_engine.md).
STT_MODEL_SIZE = "base"

# Transcriptions récentes gardées en mémoire : re-transcrire deux fois
# le même extrait coûte plusieurs secondes de calcul pour rien.
STT_CACHE_SIZE: int = 20

# --- API ---
# ⚠️ 127.0.0.1 : l'API n'est joignable que depuis ce PC. Elle n'a aucune
# authentification, et GET /history renvoie l'intégralité des
# conversations — l'exposer au réseau local la rendrait lisible par tout
# appareil du WiFi.
# À REVOIR EN PHASE 5 (mobile/PWA) : passer à 0.0.0.0 exigera d'abord un
# jeton partagé, sinon le téléphone ouvre la porte à tout le réseau.
# Décision actée le 01/08/2026, voir ROADMAP.md §5.1.
API_HOST = "127.0.0.1"
API_PORT = 8000

# --- Sécurité : mémoire des comportements ---
# Période d'apprentissage : les capteurs observent sans alerter pendant
# ce délai après la création de l'historique. Sans elle, le premier
# balayage signalerait chaque programme de la machine comme « nouveau »,
# et le rapport deviendrait illisible.
SECURITY_LEARNING_HOURS: int = 24

# Au-delà, un comportement non revu est oublié. Son retour redevient donc
# un signal, et le fichier ne grossit pas indéfiniment.
SECURITY_HISTORY_RETENTION_DAYS: int = 30

# --- Sécurité : surveillance rançongiciel ---
# Répertoires surveillés, relatifs au profil utilisateur. Seules les
# métadonnées sont lues (noms, extensions, dates) — jamais le contenu
# des documents. Voir security/ransomware_watch.py.
RANSOMWARE_WATCH_DIRS = ["Documents", "Desktop", "Pictures"]

# Seuil de « rafale » : nombre de fichiers modifiés dans la fenêtre
# ci-dessous au-delà duquel on signale. Une sauvegarde ou une synchro
# déclenchent le même motif, d'où un simple avertissement.
RANSOMWARE_BURST_THRESHOLD: int = 50
RANSOMWARE_BURST_WINDOW_MINUTES: int = 5

# Borne de parcours, répartie entre les répertoires surveillés : un
# balayage qui met deux minutes ne serait jamais lancé. Au-delà, le
# rapport signale explicitement qu'il est incomplet.
# Mesuré sur cette machine : ~9 200 fichiers parcourus en 1,4 s.
RANSOMWARE_MAX_FILES_SCANNED: int = 30000

# --- RAG : seuil de pertinence ---
# ⚠️ Une recherche vectorielle ne renvoie JAMAIS « rien » : ChromaDB rend
# toujours ses n plus proches voisins, même si le plus proche parle d'autre
# chose. Sans ce seuil, le RAG injectait un extrait hors sujet en
# l'annonçant comme « contexte trouvé dans les documents » — le LLM le
# croyait et ignorait ce qui avait été lu à l'écran.
#
# Distance COSINUS, pas L2. La collection était en L2 par défaut, dont les
# distances mesurées allaient de 150 à 700 et dépendaient de la longueur
# des textes — un seuil absolu y aurait été un nombre magique intenable.
# Le cosinus est borné [0, 2] et indépendant de la longueur.
#
# Calibré sur la base réelle :
#     pertinent   0,174  0,290  0,416
#     hors sujet  0,449  0,458  0,479  0,487
# ⚠️ Marge étroite, mesurée sur 2 chunks d'un document d'exemple.
#
# ⚠️ VALEUR PROBABLEMENT TROP PERMISSIVE. Vérifié sur un corpus de test
# plus réaliste (trois documents distincts : congés, assurance, matériel) :
#     pertinent   0,236 … 0,346
#     hors sujet  0,396 … 0,474   ← quatre d'entre elles passeraient à 0,45
# Le seuil qui sépare correctement ces deux populations est ~0,37. La
# valeur n'est PAS changée ici parce que ces documents sont fabriqués :
# c'est sur les vrais documents de Cyril que la mesure compte.
#
# Pour recalibrer, une fois de vrais documents indexés :
#     venv\Scripts\python.exe demos\calibrate_rag.py
# Le script rédige lui-même les questions de contrôle depuis les extraits
# indexés, mesure les deux populations et propose la valeur à reporter ici.
#
# Ce seuil reste le SECOND verrou : le premier est core/intent.py, qui
# empêche la plupart des questions hors sujet d'atteindre le RAG — c'est
# pourquoi une valeur imparfaite dégrade sans casser.
RAG_MAX_DISTANCE: float = 0.45

# --- Intention : écran, documents, ou ni l'un ni l'autre ---
# Les listes de mots-clés couvraient 50 % des formulations réelles et ne
# pouvaient pas faire mieux : « c'est écrit quoi ? » ne contient aucun mot
# désignant l'écran. Un classifieur local tranche à 0,14 s par message
# (voir OLLAMA_HOST). Voir core/intent.py.
#
# ⚠️ Ce classifieur ne décide QUE d'une capacité (quelle source consulter).
# La décision de sécurité — donnée sensible, donc local forcé — reste aux
# mots-clés déterministes de router.is_sensitive(). Voir CLAUDE.md règle 3.
INTENT_CLASSIFIER_ENABLED: bool = True
INTENT_MODEL = "qwen2.5:7b"

# Court volontairement : au-delà, le repli sur les mots-clés est préférable
# à faire attendre Cyril. Le classifieur ne doit jamais bloquer une réponse.
INTENT_TIMEOUT_SECONDS: float = 5.0

# --- Mémoire ---
DB_PATH = "memory/orion_memory.db"
MAX_HISTORY_MESSAGES = 100      # garde les 100 derniers messages max

# Historique joint à une requête CLOUD : volontairement bien plus court que
# MAX_HISTORY_MESSAGES. Limite ce qui sort de la machine tout en gardant le
# fil de la conversation. Voir CLAUDE.md règle 3.
CLOUD_HISTORY_MESSAGES: int = 6

# Nombre d'événements système récents injectés dans le prompt (mémoire
# enrichie, ROADMAP Phase 2). Volontairement bas : il s'agit de donner du
# contexte au LLM, pas de lui déverser un journal. Jamais joint à une
# requête cloud — voir OrionCore._build_messages().
RECENT_EVENTS_IN_PROMPT: int = 5

# Historique joint quand la VISION se déclenche. Mesuré sur la base réelle
# de Cyril (100 messages), en injectant un texte d'écran sans ambiguïté et
# en comptant les réponses qui le citent, 3 tirages par question :
#     100 messages  ->  0/9   Luca's demande « décris-moi ton écran »
#      16 messages  ->  9/9
#      10 messages  ->  7/9
#       6 messages  ->  9/9
# La cause n'est pas la fenêtre de contexte : l'historique contenait 12
# réponses « pourriez-vous me donner plus de contexte ». Cent messages de
# ce motif sont un exemple d'apprentissage qui enseigne au modèle le
# réflexe exact qu'on cherche à supprimer.
# ⚠️ Vérifié aussi : ajouter un rappel APRÈS la question ne corrige rien
# (0/9 à 100 messages). C'est la longueur seule qui décide.
# Quand Cyril interroge son écran, l'écran est le sujet ; quelques tours
# suffisent à garder le fil de la conversation.
VISION_HISTORY_MESSAGES: int = 6

# --- Identité de Luca's ---
SYSTEM_PROMPT = (
    "Tu es Luca's, l'assistant personnel de Cyril. "
    "Réponds toujours en français, de façon claire, directe et utile."
)

# --- UI ---
WINDOW_TITLE = "Luca's"
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 650
