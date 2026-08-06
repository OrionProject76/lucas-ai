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

# ⚠️ Le paquet `duckduckgo_search` est déprécié et renommé `ddgs` — trouvé
# le 04/08/2026 en câblant ce module dans le chat : `duckduckgo_search`
# 8.1.1 tournait sans erreur mais ne renvoyait plus AUCUN résultat, même
# sur la requête d'exemple de ce fichier (« intelligence artificielle »).
# `ddgs` (même API, from ddgs import DDGS) renvoie de vrais résultats.
from ddgs import DDGS

from core.text_utils import contains_any, normalize

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

    # ⚠️ NORMALISÉ AUSSI DEPUIS LE 05/08/2026 — c'était une vraie fuite.
    #
    # Les deux motifs ci-dessus codent l'espace ASCII en dur :
    # `(?:[ ]?[A-Z0-9])` et `(?:\d[ -]?)`. Appliqués à la chaîne BRUTE,
    # ils ne voyaient rien dès que les séparateurs n'étaient pas des
    # espaces ASCII. Mesuré :
    #
    #   "FR76 3000 4000 0512 3456 7890 123"            -> bloqué
    #   "FR76<NBSP>3000<NBSP>4000<NBSP>…"              -> PASSAIT ⚠️
    #   "4539<NBSP>1488<NBSP>0343<NBSP>6467" (carte)   -> PASSAIT ⚠️
    #   "4539‑1488‑0343‑6467" (tiret insécable)        -> PASSAIT ⚠️
    #
    # Ce n'est pas un cas de laboratoire : les sites bancaires et les PDF
    # affichent couramment les IBAN avec des espaces INSÉCABLES,
    # précisément pour que le numéro ne soit pas coupé en fin de ligne.
    # Un copier-coller depuis la banque emporte donc ces caractères — et
    # c'est exactement le geste qu'on fait pour poser une question sur
    # son IBAN.
    #
    # `normalize()` replie les catégories Unicode Zs (tout espace) et Pd
    # (tout tiret) vers leurs équivalents ASCII, ce qui rend les motifs
    # existants opérants sans les réécrire. Il met aussi en minuscules :
    # sans effet ici, IBAN_PATTERN portant déjà re.IGNORECASE et
    # LONG_NUMBER_PATTERN ne visant que des chiffres.
    normalized = normalize(query)
    return bool(
        IBAN_PATTERN.search(normalized) or LONG_NUMBER_PATTERN.search(normalized)
    )


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
        except Exception as e:
            # faire tomber l'appelant : on dégrade, on ne plante pas.
            logger.error("Erreur recherche web : %s", e)
            return [{
                "title": "Erreur",
                "href": "",
                "body": f"Impossible de rechercher : {e}",
            }]

    def get_summary_with_outcome(
        self, query: str, max_results: int = 3
    ) -> tuple[str, str]:
        """
        Résumé texte ET issue réelle de la recherche.

        ⚠️ Pourquoi cette méthode existe (05/08/2026, audit « silence qui
        laisse le modèle deviner », ROADMAP.md §5.39).

        `get_summary()` rend une chaîne dans TOUS les cas — succès, zéro
        résultat, panne réseau, ou refus pour données identifiantes. Vue
        de l'appelant, ces quatre situations étaient indiscernables. Et
        `core/lucas_core.py` les injectait toutes sous la même étiquette :

            « RECHERCHE WEB RÉELLE (DuckDuckGo) : ...
              Appuie-toi UNIQUEMENT sur ces résultats réels. »

        Autrement dit, un refus de confidentialité ou une panne DNS
        arrivaient au modèle présentés comme de vrais résultats de
        recherche, avec l'ordre de s'en servir. Ce n'est pas un silence,
        c'est pire : une étiquette fausse. Même famille que §5.31 —
        l'appelant ne doit jamais avoir à deviner ce qui s'est passé.

        Issues possibles : "ok", "empty", "failed", "refused".
        """
        results = self.search(query, max_results)

        if not results:
            return f'Aucun résultat pour « {query} ».', "empty"

        # `search()` encode ces deux situations dans un faux résultat plutôt
        # que par une exception (choix d'origine : ne jamais faire tomber
        # l'appelant). On les redistingue ici, à la source, plutôt que de
        # laisser chaque appelant renifler des chaînes.
        premier_titre = (results[0].get("title") or "").lower()
        if premier_titre == "recherche annulée":
            return results[0].get("body") or REFUSAL_MESSAGE, "refused"
        if premier_titre == "erreur":
            return results[0].get("body") or "Recherche impossible.", "failed"

        return self.get_summary(query, max_results), "ok"

    def get_summary(self, query: str, max_results: int = 3) -> str:
        """
        Résumé texte des résultats, prêt à afficher ou à prononcer.

        ⚠️ Ne distingue PAS succès, échec et refus — voir
        `get_summary_with_outcome()`, à préférer dès qu'on doit agir
        différemment selon l'issue. Conservé tel quel pour les appelants
        qui ne veulent qu'un texte à montrer.
        """
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
