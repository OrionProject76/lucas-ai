# core/router.py — décide si la question part en local ou (plus tard) en cloud
# + décide si le RAG (documents personnels) doit être consulté

KEYWORDS_CLOUD = [
    "analyse", "compare", "projection",
    "20 ans", "stratégie", "risque",
    "portfolio", "optimise",
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


def route(text: str) -> str:
    """Décide local vs cloud — inchangé."""
    text_lower = text.lower()
    if any(keyword in text_lower for keyword in KEYWORDS_CLOUD):
        return "cloud"
    return "local"


def should_use_rag(text: str) -> bool:
    """
    Décide si on va chercher dans les documents personnels (RAG) avant
    de répondre. Axe de décision indépendant de route() — une question
    peut être locale ET utiliser le RAG, ou cloud sans RAG, etc.
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in KEYWORDS_RAG)
