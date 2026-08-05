# core/local_llm.py — parle au modèle local via Ollama (version non-streaming, utilisée en secours)

import requests

from config import MODEL_NAME, OLLAMA_URL
from core.ollama_client import OllamaModelMissing, post_chat
from core.ollama_reply import extract_reply


def ask_local(messages: list[dict]) -> str:
    """
    messages : liste de dicts {"role": "user"/"assistant"/"system", "content": "..."}
    Retourne toujours une string (jamais d'exception qui remonte à l'UI).
    """
    try:
        response = post_chat(
            OLLAMA_URL,
            {"model": MODEL_NAME, "messages": messages, "stream": False},
            timeout=60,
        )
        # ⚠️ Deux pannes DIFFÉRENTES, deux messages différents — la
        # confusion entre les deux a été attrapée par un test existant.
        #
        # 1. Pas de clé "message" du tout : Ollama a renvoyé une forme
        #    inattendue (modèle absent, version incompatible). Le KeyError
        #    ci-dessous part dans le `except (KeyError, ValueError)`, qui
        #    dit à Cyril de vérifier son installation.
        message = response.json()["message"]

        # 2. Un message bien formé mais sans réponse exploitable : les
        #    modèles à raisonnement explicite (gpt-oss:20b) rendent parfois
        #    un `content` VIDE et tout leur texte dans `thinking` — mesuré
        #    2 fois sur 16 (ROADMAP.md §5.44). Rien à voir avec une
        #    installation cassée, donc rien à voir dans le message.
        reponse = extract_reply(message)
        if not reponse:
            # Ne jamais rendre une chaîne vide en silence : côté Cyril,
            # c'est indiscernable d'une panne. Même doctrine que §5.39.
            return (
                "[Erreur] Le modèle a raisonné sans produire de réponse "
                "exploitable. Reformule la question, ou pose-la plus "
                "simplement."
            )
        return reponse

    except OllamaModelMissing as e:
        return f"[Erreur] {e}"
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