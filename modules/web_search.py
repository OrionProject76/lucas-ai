# modules/web_search.py — recherche web via DuckDuckGo
#
# ⚠️ SORTIE RÉSEAU : chaque requête part chez DuckDuckGo. C'est la
# troisième surface par laquelle du texte quitte la machine, après le LLM
# cloud et edge_tts.
#
# Le filtre ci-dessous est VOLONTAIREMENT plus étroit que le
# KEYWORDS_SENSITIVE de core/router.py. Réutiliser celui-ci
# sur-bloquerait : « quel est le meilleur crédit immobilier » ou
# « comment changer de banque » sont des recherches parfaitement
# légitimes que les mots « crédit » et « banque » feraient refuser. Un
# filtre qui empêche l'usage normal finit désactivé, donc inutile.
#
# On ne bloque donc que ce qui est réellement IDENTIFIANT : un IBAN, un
# numéro de carte, le solde d'un compte précis. Décision de Cyril du
# 01/08/2026, voir ROADMAP.md §5.1.

import logging
import re

from duckduckgo_search import DDGS

from core.text_utils import contains_any

logger = logging.getLogger(__name__)

SNIPPET_LENGTH = 150

# Expressions qui désignent les données propres de Cyril, et non un sujet
# de recherche. « mon solde » n'a aucun sens comme requête web.
IDENTIFYING_KEYWORDS = (
    "mon iban", "mon rib", "mon solde", "mon compte", "mes comptes",
    "mon numéro de carte", "ma carte bancaire", "mon numéro de compte",
    "mon code pin", "mon mot de passe", "mon numéro de sécurité sociale",
    "mon relevé", "mes relevés",
)

# Un IBAN français : FR suivi de 2 chiffres de contrôle puis 10 à 27
# caractères alphanumériques, espaces tolérés.
IBAN_PATTERN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){10,27}\b", re.IGNORECASE)

# Une suite de 13 à 19 chiffres, groupés ou non : numéro de carte ou de
# compte. Les années et montants courants n'atteignent pas cette longueur.
LONG_NUMBER_PATTERN = re.compile(r"\b(?:\d[ -]?){13,19}\b")

REFUSAL_MESSAGE = (
    "Recherche annulée : la requête contient une donnée personnelle "
    "identifiante. Une recherche web part chez DuckDuckGo — ce type "
    "d'information ne doit pas quitter la machine."
)


def is_identifying(query: str) -> bool:
    """
    Vrai si la requête contient une donnée propre à Cyril plutôt qu'un
    sujet de recherche. Volontairement étroit : voir l'en-tête du module.
    """
    # Normalisé : « mon releve » sans accent contournait le filtre et
    # partait chez DuckDuckGo (voir core/text_utils.py).
    if contains_any(query, IDENTIFYING_KEYWORDS):
        return True
    return bool(IBAN_PATTERN.search(query) or LONG_NUMBER_PATTERN.search(query))


class WebSearch:
    """
    Recherche web. Retourne toujours une structure exploitable.

    `log_event` est injecté, comme ailleurs : un refus est un fait à
    tracer, sinon Cyril ne comprend pas pourquoi rien n'est revenu.
    """

    def __init__(self, log_event=None) -> None:
        self.log_event = log_event

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """
        Retourne une liste de résultats {title, href, body}.

        Une requête contenant une donnée identifiante est refusée avant
        tout appel réseau : rien ne part chez DuckDuckGo.

        Une instance DDGS est créée par appel : la bibliothèque gère une
        session HTTP, et la garder ouverte entre deux recherches
        espacées de plusieurs heures menait à des sessions expirées.
        """
        if is_identifying(query):
            if self.log_event is not None:
                self.log_event("websearch_refused", query[:80])
            return [{"title": "Recherche annulée", "href": "", "body": REFUSAL_MESSAGE}]

        try:
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))
        except Exception as e:  # noqa: BLE001 — le réseau ne doit jamais
            # faire tomber l'appelant : on dégrade, on ne plante pas.
            logger.error("Erreur recherche web : %s", e)
            return [{
                "title": "Erreur",
                "href": "",
                "body": f"Impossible de rechercher : {e}",
            }]

    def get_summary(self, query: str, max_results: int = 3) -> str:
        """Résumé texte des résultats, prêt à afficher ou à prononcer."""
        results = self.search(query, max_results)

        if not results:
            return f'Aucun résultat pour « {query} ».'

        lines = [f'Résultats pour « {query} » :']
        for i, result in enumerate(results, 1):
            title = result.get("title") or "Sans titre"
            href = result.get("href") or ""
            body = result.get("body") or "Pas de description"

            lines.append(f"{i}. {title} - {href}")
            snippet = body[:SNIPPET_LENGTH]
            suffix = "..." if len(body) > SNIPPET_LENGTH else ""
            lines.append(f"   {snippet}{suffix}")
        return "\n".join(lines)


if __name__ == "__main__":
    print(WebSearch().get_summary("intelligence artificielle"))
