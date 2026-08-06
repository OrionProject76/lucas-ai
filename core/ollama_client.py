# core/ollama_client.py — accès HTTP à Ollama, avec reprise sur 404
#
# ── Pourquoi ce module existe ─────────────────────────────────────────
#
# Des « 404 model not found » intermittents apparaissaient au démarrage,
# sur un modèle pourtant présent dans `ollama list`. Deux causes
# distinctes, longtemps confondues :
#
#   1. Le doublon d'instances Ollama (documenté dans CLAUDE.md) — réglé
#      séparément, ce n'était pas celle-ci.
#
#   2. La résolution implicite du tag. `MODEL_NAME` valait « qwen2.5 »,
#      qui ne correspond à AUCUN modèle exactement : Ollama devine
#      « qwen2.5:latest ». Cette résolution échoue tant que son registre
#      n'est pas entièrement chargé — d'où des 404 juste après le
#      démarrage du service, puis plus rien.
#
# Le tag est désormais explicite dans config.py. Ce module ajoute la
# ceinture : une reprise unique sur 404, le temps qu'Ollama finisse de
# s'initialiser.

import time

import requests

# Une seule reprise, après une courte pause : si le modèle est vraiment
# absent, insister ne le fera pas apparaître et retarderait le message
# d'erreur utile.
RETRY_DELAY_SECONDS = 1.5


class OllamaModelMissing(Exception):
    """Le modèle demandé reste introuvable après reprise."""


def post_chat(url: str, payload: dict, timeout, stream: bool = False):
    """
    Envoie une requête à Ollama, avec une reprise sur 404.

    Retourne la réponse `requests`. Lève OllamaModelMissing si le modèle
    reste introuvable — avec le nom exact et la commande pour l'installer,
    plutôt qu'un « 404 » que rien n'explique.
    """
    response = requests.post(url, json=payload, stream=stream, timeout=timeout)

    if response.status_code == 404:
        # Laisser à Ollama le temps de finir de charger son registre.
        time.sleep(RETRY_DELAY_SECONDS)
        response = requests.post(url, json=payload, stream=stream, timeout=timeout)

    if response.status_code == 404:
        model = payload.get("model", "?")
        raise OllamaModelMissing(
            f"Modèle « {model} » introuvable pour Ollama.\n"
            f"  • Vérifier qu'il est installé : ollama list\n"
            f"  • L'installer au besoin : ollama pull {model}\n"
            f"  • Vérifier qu'une seule instance tourne : tasklist | findstr ollama"
        )

    response.raise_for_status()
    return response


def is_ready(base_url: str, timeout: float = 3.0) -> bool:
    """Ollama répond-il et a-t-il au moins un modèle enregistré ?"""
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=timeout)
        return bool(response.json().get("models"))
    except Exception:  # noqa: BLE001 — indisponible = pas prêt
        return False
