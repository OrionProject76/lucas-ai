# core/router.py — décide si la question part en local (Ollama) ou en cloud
# + décide si le RAG (documents personnels) doit être consulté
# Architecture hybride : local par défaut, cloud pour les questions complexes,
# jamais de donnée sensible vers le cloud (CLAUDE.md règle 3).

KEYWORDS_CLOUD = [
    "analyse", "compare", "projection",
    "20 ans", "stratégie", "optimise",
]

# Mots-clés qui signalent une donnée ultra-sensible (finance personnelle,
# documents privés, identité). Ces questions restent LOCALES même si elles
# contiennent aussi un mot-clé cloud — voir route() et CLAUDE.md règle 3.
# "portfolio" et "risque" étaient dans KEYWORDS_CLOUD : ce sont des termes
# de finance perso, ils ont été déplacés ici le 01/08/2026.
KEYWORDS_SENSITIVE = [
    "portfolio", "risque", "budget", "dépense", "salaire",
    "revenu", "compte bancaire", "banque", "économies",
    "impôt", "relevé", "transaction", "iban", "crédit",
    "emprunt", "mot de passe", "carte bancaire",
    "mon contrat", "ma facture",
]

# Mots-clés qui signalent que la question porte probablement sur des
# documents personnels de Cyril plutôt que sur une connaissance générale.
# Volontairement simple (mots-clés, pas de classification LLM) — cohérent
# avec le principe "pas de sur-ingénierie avant que les bases soient stables".
KEYWORDS_RAG = [
    "document", "fichier", "mes notes", "mes docs",
    "dans le pdf", "résume le", "résume mon",
    "d'après le document", "que dit le document",
    "rappelle-moi ce que",
]


def is_sensitive(text: str) -> bool:
    """
    Décide si la question porte sur des données ultra-sensibles (finance
    personnelle, documents privés, identité). Même approche volontairement
    simple que should_use_rag() : mots-clés, pas de classification LLM.
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in KEYWORDS_SENSITIVE)


def route(text: str) -> str:
    """
    Décide si la question part en local (Ollama) ou en cloud.

    Ordre de priorité — le local est le défaut sûr, le cloud l'exception :
      1. donnée sensible détectée  -> local, même si un mot-clé cloud est
         présent (« analyse mon portfolio » reste local)
      2. question sur les documents personnels (RAG) -> local
      3. question sur le contenu de l'écran -> local
      4. question complexe (mot-clé cloud) -> cloud
      5. tout le reste -> local

    Voir CLAUDE.md règle 3 pour la règle projet correspondante.
    """
    if is_sensitive(text):
        return "local"
    if should_use_rag(text):
        return "local"
    # L'image ne part jamais au cloud, mais sa DESCRIPTION en dirait tout
    # autant : « une fenêtre de banque affichant un solde de 3200 € ».
    if should_use_vision(text):
        return "local"

    text_lower = text.lower()
    if any(keyword in text_lower for keyword in KEYWORDS_CLOUD):
        return "cloud"
    return "local"


# Mots-clés qui signalent que la question porte sur ce qui est affiché à
# l'écran. Volontairement spécifiques : « regarde » seul déclencherait sur
# « regarde si tu peux m'aider », et capturer l'écran à chaque message
# coûterait plusieurs secondes de VLM pour rien.
KEYWORDS_VISION = [
    "à l'écran", "a l'écran", "sur mon écran", "mon écran",
    "que vois-tu", "qu'est-ce que tu vois", "tu vois quoi",
    "regarde mon écran", "regarde ça", "regarde cette",
    "cette erreur", "ce message d'erreur", "cette fenêtre",
    "sous les yeux", "capture d'écran", "screenshot",
]


def should_use_vision(text: str) -> bool:
    """
    Décide si Luca's doit regarder l'écran avant de répondre.

    Même approche que should_use_rag() : mots-clés, pas de classification
    LLM. Une capture + analyse VLM coûte plusieurs secondes, on ne la
    déclenche donc que sur une demande explicite.
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in KEYWORDS_VISION)


def route_voice(answer: str, question: str = "") -> str:
    """
    Décide quel moteur TTS prononce la réponse : "local" (Piper) ou
    "cloud" (edge_tts).

    ⚠️ Le défaut est le CLOUD, à l'inverse de route(). Ce n'est pas une
    erreur : edge_tts a la meilleure voix, et le TTS ne transmet que du
    texte déjà affiché à l'écran. Le local est forcé dès qu'un contenu
    sensible est détecté.

    L'analyse porte sur la question ET la réponse : « quel est mon
    salaire ? » → « il est de 3200 euros » ne contient aucun mot-clé
    sensible dans la réponse seule, mais reste une donnée à ne pas
    envoyer chez Microsoft.

    Voir CLAUDE.md règle 3, section TTS.
    """
    combined = f"{question} {answer}"
    if is_sensitive(combined) or should_use_rag(combined):
        return "local"
    return "cloud"


def should_use_rag(text: str) -> bool:
    """
    Décide si on va chercher dans les documents personnels (RAG) avant
    de répondre. Axe de décision indépendant de route() — une question
    peut être locale ET utiliser le RAG, ou cloud sans RAG, etc.
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in KEYWORDS_RAG)
