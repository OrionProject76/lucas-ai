# config.py — tous les réglages d'Orion au même endroit

# --- IA locale (Ollama) ---
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5"

# Liste des modèles disponibles (pour futur sélecteur)
AVAILABLE_MODELS = ["qwen2.5", "llama3.2", "mistral", "codellama"]

# --- Timeouts ---
OLLAMA_CONNECT_TIMEOUT = 10   # secondes pour se connecter à Ollama
OLLAMA_READ_TIMEOUT = 120     # secondes pour recevoir la réponse

# --- IA cloud (optionnel, désactivé pour l'instant) ---
OPENAI_API_KEY = ""

# --- Mémoire ---
DB_PATH = "memory/orion_memory.db"
MAX_HISTORY_MESSAGES = 100      # garde les 100 derniers messages max

# --- Identité d'Orion ---
SYSTEM_PROMPT = (
    "Tu es Orion, l'assistant personnel de Cyril. "
    "Réponds toujours en français, de façon claire, directe et utile."
)

# --- UI ---
WINDOW_TITLE = "Orion AI"
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 650
