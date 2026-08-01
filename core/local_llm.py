# core/local_llm.py — parle au modèle local via Ollama (version non-streaming, utilisée en secours)

import requests
from config import OLLAMA_URL, MODEL_NAME


def ask_local(messages: list[dict]) -> str:
    """
    messages : liste de dicts {"role": "user"/"assistant"/"system", "content": "..."}
    Retourne toujours une string (jamais d'exception qui remonte à l'UI).
    """
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "stream": False,
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    except requests.exceptions.ConnectionError:
        return (
            "[Erreur] Impossible de contacter Ollama sur "
            f"{OLLAMA_URL}. Vérifie qu'Ollama tourne (commande : ollama serve)."
        )
    except requests.exceptions.RequestException as e:
        return f"[Erreur] Problème réseau avec Ollama : {e}"
    except (KeyError, ValueError):
        return (
            f"[Erreur] Réponse inattendue d'Ollama. "
            f"Vérifie que le modèle '{MODEL_NAME}' est bien installé (commande : ollama list)."
        )