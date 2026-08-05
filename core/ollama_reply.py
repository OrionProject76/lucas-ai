# core/ollama_reply.py — extrait la réponse utile d'un message Ollama
#
# ── Pourquoi ce module existe (05/08/2026) ────────────────────────────
#
# Les modèles à raisonnement explicite (gpt-oss:20b, deepseek-r1, et la
# famille qui suivra) ne rendent plus UN champ mais DEUX :
#
#     {"role": "assistant",
#      "thinking": "User asked ... we must answer in French ...",
#      "content":  "qu'il résolût"}
#
# Tout le projet lisait `message["content"]` — ce qui est juste dans le
# cas normal, et **rend une chaîne vide** quand le modèle épuise son
# raisonnement sans produire de réponse finale.
#
# Ce n'est pas théorique, c'est mesuré sur cette machine (ROADMAP.md
# §5.44) : **2 réponses vides sur 16** avec gpt-oss:20b, dont une avec
# **11 400 caractères** de `thinking` pour zéro `content`. Côté Cyril,
# ça se voit comme une réponse vide — sans erreur, sans explication.
#
# Pire, et c'est ce qui a rendu le problème visible : le classifieur
# d'intention (`core/intent.py`) tombait sur ce cas et **repartait en
# repli mots-clés sans le dire**. Trois formulations sur douze étaient
# mal classées, non parce que le modèle se trompait, mais parce que sa
# réponse n'était jamais lue.
#
# ── Ce que ce module fait, et ce qu'il refuse de faire ────────────────
#
# Il rend `content` quand il existe. Sinon, et seulement sinon, il tente
# de récupérer une réponse dans `thinking`.
#
# ⚠️ Il ne CONCATÈNE jamais les deux. Le raisonnement d'un modèle n'est
# pas destiné à Cyril : il est en anglais, il hésite à voix haute, et il
# contient parfois des pistes explicitement abandonnées. L'afficher
# reviendrait à faire passer un brouillon pour une réponse.

from __future__ import annotations

# Un raisonnement se termine souvent par la réponse elle-même, après une
# formule de bascule. On ne garde que ce qui suit la DERNIÈRE.
_MARQUEURS_CONCLUSION = (
    "final answer:",
    "answer:",
    "réponse finale :",
    "reponse finale :",
    "donc :",
)

# Au-delà, ce n'est plus une réponse récupérée mais un brouillon entier.
# Une vraie réponse de Luca tient largement dans cette limite ; un
# raisonnement de gpt-oss en fait couramment 10 000.
_LONGUEUR_MAX_RECUPEREE = 600


def extract_reply(message: dict) -> str:
    """
    Réponse utile d'un message Ollama, `thinking` compris si nécessaire.

    Rend une chaîne vide si rien d'exploitable — l'appelant doit alors le
    DIRE plutôt que d'afficher du vide (même doctrine que §5.39).
    """
    if not isinstance(message, dict):
        return ""

    contenu = (message.get("content") or "").strip()
    if contenu:
        return contenu

    pensee = (message.get("thinking") or "").strip()
    if not pensee:
        return ""

    # Une conclusion explicite dans le raisonnement est la meilleure
    # récupération possible : c'est le modèle lui-même qui désigne sa
    # réponse.
    minuscules = pensee.lower()
    for marqueur in _MARQUEURS_CONCLUSION:
        position = minuscules.rfind(marqueur)
        if position != -1:
            candidat = pensee[position + len(marqueur):].strip()
            if candidat and len(candidat) <= _LONGUEUR_MAX_RECUPEREE:
                return candidat

    # Sinon, le dernier paragraphe non vide — c'est là que ces modèles
    # posent leur conclusion quand ils n'annoncent pas de marqueur.
    for paragraphe in reversed(pensee.split("\n\n")):
        candidat = paragraphe.strip()
        if candidat and len(candidat) <= _LONGUEUR_MAX_RECUPEREE:
            return candidat

    # Raisonnement long et sans conclusion isolable : ne RIEN rendre
    # plutôt qu'un brouillon de 11 000 caractères présenté comme une
    # réponse. L'appelant traitera ce vide explicitement.
    return ""
