# modules/web_search.py — recherche web via DuckDuckGo
#
# ⚠️ SORTIE RÉSEAU : chaque requête part chez DuckDuckGo. C'est la
# troisième surface par laquelle du texte quitte la machine, après le LLM
# cloud et edge_tts. Contrairement aux deux autres, elle n'a AUCUN garde-
# fou de sensibilité aujourd'hui — voir la note dans ROADMAP.md, la
# décision revient à Cyril (sur-blocage probable si on réutilise
# is_sensitive() tel quel).

import logging

from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

SNIPPET_LENGTH = 150


class WebSearch:
    """Recherche web. Retourne toujours une structure exploitable."""

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """
        Retourne une liste de résultats {title, href, body}.

        Une instance DDGS est créée par appel : la bibliothèque gère une
        session HTTP, et la garder ouverte entre deux recherches
        espacées de plusieurs heures menait à des sessions expirées.
        """
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
