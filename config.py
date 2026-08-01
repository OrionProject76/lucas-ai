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
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5"

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
EDGE_TTS_VOICE = "fr-FR-HenriNeural"   # voix cloud Microsoft (défaut)
PIPER_VOICE = "fr_FR-upmc-medium"      # voix locale, masculine comme Henri
PIPER_VOICES_DIR = "data/voices"       # modèles .onnx (non versionnés)

# Voix Piper également téléchargée, pour comparer à l'oreille :
# "fr_FR-siwis-medium" (féminine)

# ⚠️ SÉCURITÉ — laisser à False sauf décision consciente.
# À True, si Piper est indisponible (modèle manquant, erreur de chargement),
# un texte SENSIBLE est prononcé par edge_tts, donc envoyé à Microsoft.
# À False, ce texte n'est simplement pas prononcé et l'événement est loggué.
# Voir CLAUDE.md règle 3, section TTS.
TTS_ALLOW_CLOUD_ON_SENSITIVE: bool = False

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

# --- Identité de Luca's ---
SYSTEM_PROMPT = (
    "Tu es Luca's, l'assistant personnel de Cyril. "
    "Réponds toujours en français, de façon claire, directe et utile."
)

# --- UI ---
WINDOW_TITLE = "Luca's"
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 650
