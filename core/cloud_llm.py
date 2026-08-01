# core/cloud_llm.py — IA cloud, désactivée pour l'instant

from config import OPENAI_API_KEY


def ask_cloud(messages: list[dict]) -> str:
    if not OPENAI_API_KEY:
        return "[Cloud non configuré] Ajoute ta clé API dans config.py pour activer ce mode."
    return "[Cloud] Fonction pas encore implémentée."