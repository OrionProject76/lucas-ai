# modules/finance_categorizer.py — catégorisation des transactions bancaires
#
# ⚠️ SÉCURITÉ : les libellés de transaction sont des données ultra-sensibles
# (CLAUDE.md règle 3). La catégorisation par LLM passe donc EXCLUSIVEMENT par
# ask_local() — jamais par OrionCore.ask(), qui route et pourrait choisir le
# cloud. Aucun libellé bancaire ne doit atteindre un serveur externe.
#
# Deux étages : règles par mots-clés d'abord (déterministe, gratuit, hors
# ligne), LLM local seulement pour ce que les règles n'ont pas reconnu.

import unicodedata
from collections.abc import Callable

UNCATEGORIZED = "Non catégorisé"

# Catégories fermées : le LLM doit choisir dans cette liste, pas inventer.
CATEGORIES = [
    "Logement",
    "Alimentation",
    "Transport",
    "Santé",
    "Loisirs",
    "Abonnements",
    "Revenus",
    "Autre",
]

# Mots-clés en minuscules et sans accents (voir _normalize).
KEYWORD_RULES: dict[str, list[str]] = {
    "Logement": [
        "loyer", "edf", "engie", "electricite", "gaz", "veolia", "eau",
        "assurance habitation", "syndic", "charges copro", "taxe fonciere",
    ],
    "Alimentation": [
        "carrefour", "leclerc", "auchan", "lidl", "aldi", "intermarche",
        "monoprix", "franprix", "casino", "boulangerie", "boucherie",
        "restaurant", "uber eats", "deliveroo", "supermarche",
    ],
    "Transport": [
        "sncf", "ratp", "essence", "carburant", "total", "shell", "esso",
        "uber", "peage", "parking", "autoroute", "navigo", "blablacar",
    ],
    "Santé": [
        "pharmacie", "medecin", "docteur", "mutuelle", "hopital",
        "dentiste", "laboratoire", "opticien", "cpam",
    ],
    "Loisirs": [
        "cinema", "fnac", "decathlon", "steam", "playstation", "concert",
        "musee", "theatre", "librairie",
    ],
    "Abonnements": [
        "netflix", "spotify", "deezer", "free", "orange", "sfr",
        "bouygues", "canal+", "amazon prime", "disney", "abonnement",
    ],
    "Revenus": [
        "salaire", "paie", "virement recu", "remboursement", "prime",
        "allocation", "caf", "pole emploi", "dividende",
    ],
}


def _normalize(text: str) -> str:
    """Minuscules sans accents — « Électricité » et « electricite » matchent."""
    lowered = text.lower()
    decomposed = unicodedata.normalize("NFD", lowered)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def categorize_by_rules(label: str) -> str | None:
    """
    Catégorie déduite des mots-clés, ou None si aucun ne correspond.
    None (et pas "Autre") : l'appelant doit pouvoir distinguer « rien
    trouvé » de « classé comme divers », pour décider s'il interroge le LLM.
    """
    normalized = _normalize(label)
    for category, keywords in KEYWORD_RULES.items():
        if any(keyword in normalized for keyword in keywords):
            return category
    return None


def build_prompt(label: str) -> list[dict]:
    """Prompt de classification, volontairement contraint à une seule ligne."""
    categories = ", ".join(CATEGORIES)
    return [
        {
            "role": "system",
            "content": (
                "Tu classes une transaction bancaire dans une catégorie. "
                f"Réponds UNIQUEMENT par un mot de cette liste : {categories}. "
                "Aucune phrase, aucune explication, aucun autre mot."
            ),
        },
        {"role": "user", "content": f"Transaction : {label}"},
    ]


def categorize_by_llm(label: str, ask: Callable[[list[dict]], str] | None = None) -> str:
    """
    Catégorise via le LLM LOCAL. `ask` est injecté pour les tests ; par défaut
    c'est core.local_llm.ask_local, qui parle à Ollama sur localhost.

    Ne jamais passer ici une fonction qui pourrait router vers le cloud :
    un libellé bancaire ne sort pas de la machine (CLAUDE.md règle 3).

    Retourne UNCATEGORIZED si le LLM répond hors liste ou échoue — on
    préfère un trou visible à une catégorie inventée.
    """
    if ask is None:
        from core.local_llm import ask_local

        ask = ask_local

    try:
        answer = ask(build_prompt(label))
    except Exception:  # noqa: BLE001 — un LLM indisponible ne doit pas
        # faire échouer tout un import de relevé.
        return UNCATEGORIZED

    cleaned = _normalize(answer).strip(" .\n\t")
    for category in CATEGORIES:
        if _normalize(category) == cleaned:
            return category
    return UNCATEGORIZED


def categorize(
    label: str,
    use_llm: bool = True,
    ask: Callable[[list[dict]], str] | None = None,
) -> str:
    """
    Catégorise un libellé : règles d'abord, LLM local en secours.

    `use_llm=False` reste entièrement hors ligne et déterministe — utile
    pour les tests et pour un import de gros volume.
    """
    by_rules = categorize_by_rules(label)
    if by_rules is not None:
        return by_rules
    if not use_llm:
        return UNCATEGORIZED
    return categorize_by_llm(label, ask)
