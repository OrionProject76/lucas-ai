# test_rag_confidence.py — confiance/provenance étendue au RAG
#
# Gap connu depuis l'état des lieux du 04/08 : core/memory_weighting.py
# annote les souvenirs peu fiables de l'historique, mais rien d'équivalent
# n'existait côté documents. Son propre commentaire le disait : « PAS
# branché sur le RAG (...) les documents vivent dans ChromaDB avec un
# schéma de métadonnées différent qui n'a jamais eu de colonne confidence ».
#
# Ce qui a débloqué la chose sans toucher au schéma : la DISTANCE est déjà
# calculée à chaque recherche, et elle était jetée juste avant d'arriver à
# get_context(). Aucune migration de données existantes.

from __future__ import annotations

import pytest

from config import RAG_CONFIDENT_DISTANCE, RAG_MAX_DISTANCE
from modules.rag_manager import RAGManager


class _FauxRag(RAGManager):
    """
    RAGManager dont seule `search` est remplacée — `get_context` reste
    celle du vrai module, puisque c'est elle qu'on teste.
    """

    def __init__(self, resultats):
        self._resultats = resultats

    def search(self, query, top_k=3, max_distance=None, with_distances=False):
        if with_distances:
            return list(self._resultats)
        return [texte for texte, _ in self._resultats]


# ── Le seuil de confiance n'est pas le seuil d'acceptation ────────────


def test_confidence_threshold_is_stricter_than_acceptance() -> None:
    """
    Deux questions distinctes : « faut-il montrer cet extrait ? » et
    « avec quelle assurance ? ». Si les deux seuils étaient égaux, aucun
    extrait ne serait jamais marqué — le mécanisme serait décoratif.
    """
    assert RAG_CONFIDENT_DISTANCE < RAG_MAX_DISTANCE


# ── Annotation ────────────────────────────────────────────────────────


def test_a_close_extract_is_not_flagged() -> None:
    rag = _FauxRag([("Le salaire net de juillet est 1647.68 euros", 0.08)])
    contexte = rag.get_context("salaire juillet")
    assert "correspondance faible" not in contexte
    assert "1647.68" in contexte


def test_a_distant_extract_is_flagged() -> None:
    """
    Un extrait retenu à 0,32 passe le filtre de justesse. Présenté sans
    nuance, il a la même autorité qu'un extrait à 0,08 — c'est exactement
    ce que ce mécanisme corrige.
    """
    rag = _FauxRag([("Un passage vaguement proche", 0.32)])
    contexte = rag.get_context("question")
    assert "correspondance faible" in contexte


def test_the_header_warns_only_when_something_is_flagged() -> None:
    sur = _FauxRag([("extrait sûr", 0.05)])
    doute = _FauxRag([("extrait douteux", 0.31)])
    assert "ne les présente PAS comme des faits établis" not in sur.get_context("q")
    assert "ne les présente PAS comme des faits établis" in doute.get_context("q")


def test_mixed_results_flag_only_the_weak_ones() -> None:
    rag = _FauxRag([("solide", 0.05), ("douteux", 0.31)])
    # On isole les lignes « [Extrait N] » : l'en-tête cite lui aussi les
    # mots « correspondance faible » pour expliquer la marque, et le
    # confondre avec une marque ferait passer ce test à tort.
    extraits = [
        ligne for ligne in rag.get_context("q").splitlines() if ligne.startswith("[Extrait")
    ]
    solide = next(ligne for ligne in extraits if "solide" in ligne)
    douteux = next(ligne for ligne in extraits if "douteux" in ligne)
    assert "correspondance faible" not in solide
    assert "correspondance faible" in douteux


def test_a_text_fallback_match_is_never_flagged() -> None:
    """
    Distance `None` = chemin de repli textuel. Une sous-chaîne trouvée est
    une correspondance EXACTE, jamais incertaine. `None` doit se lire
    « distance inconnue », pas « distance nulle » — ni l'un ni l'autre ne
    justifie une marque de doute, mais les confondre en cacherait une.
    """
    rag = _FauxRag([("correspondance exacte", None)])
    contexte = rag.get_context("correspondance")
    assert "correspondance faible" not in contexte


def test_no_results_still_returns_an_empty_string() -> None:
    """
    Comportement historique préservé : la chaîne vide est significative,
    l'appelant n'ajoute alors aucun bloc au prompt.
    """
    assert _FauxRag([]).get_context("q") == ""


# ── Compatibilité des appelants existants ─────────────────────────────


def test_search_still_returns_plain_texts_by_default() -> None:
    """
    `with_distances` vaut False par défaut : tout appelant écrit avant le
    05/08/2026 reçoit exactement ce qu'il recevait — c'était la condition
    pour que ce chantier reste conservateur.
    """
    rag = _FauxRag([("un texte", 0.1)])
    assert rag.search("q") == ["un texte"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
