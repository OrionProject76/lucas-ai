# modules/semantic_desktop.py — organisation des documents personnels par
# sens (IDEAS.md pilier 5, catalogue #16), v1 minimal
#
# ⚠️ PÉRIMÈTRE VOLONTAIREMENT RESTREINT — décision prise en autonomie le
# 03/08/2026 (Cyril absent), pas une lecture littérale de l'idée
# catalogue. Celle-ci parle d'« auto-organisation selon habitudes » —
# c'est-à-dire déplacer/renommer de vrais fichiers de Cyril. Ça relève
# d'une action système à risque (liste blanche + confirmation, CLAUDE.md
# principe directeur), et `core/decision_engine.py` — le composant qui
# gérerait cette confirmation — n'existe pas encore. Ce module reste donc
# STRICTEMENT LECTURE SEULE : indexer/grouper/chercher, jamais déplacer,
# renommer ou modifier un fichier sur le disque de Cyril.
#
# Pas de nouvelle classification LLM non plus (« pas de GraphRAG
# complexe ») : tout repose sur l'infrastructure RAG déjà en place
# (modules/rag_manager.py — ChromaDB, embeddings Ollama, métadonnées
# `source`/`periods` déjà calculées à l'indexation) plutôt qu'un nouveau
# pipeline d'auto-tag.

from __future__ import annotations

from modules.rag_manager import RAGManager

# Marge appliquée à la recherche de documents apparentés : on demande
# plus de résultats que top_k pour pouvoir exclure les propres morceaux
# du document source sans se retrouver avec une liste trop courte.
_RELATED_SEARCH_MARGIN = 5


class SemanticDesktop:
    """
    Vue en lecture seule sur les documents déjà indexés par RAGManager,
    organisée par sens plutôt que par dossier — jamais d'écriture sur le
    disque de Cyril. Voir l'en-tête du module pour le périmètre exact.
    """

    def __init__(self, rag: RAGManager | None = None) -> None:
        self.rag = rag if rag is not None else RAGManager()

    def list_documents(self) -> list[str]:
        """Identifiants des documents actuellement indexés, triés."""
        return sorted(self.rag.indexed_documents())

    def related_documents(self, source_id: str, top_k: int = 3) -> list[str]:
        """
        Documents dont le contenu est sémantiquement proche de
        `source_id` — `source_id` lui-même toujours exclu.

        Le premier morceau indexé de `source_id` sert de requête
        représentative : interroger avec chacun de ses morceaux
        donnerait un résultat plus fin mais coûterait N requêtes pour un
        seul document, hors de propos pour un v1.
        """
        if not (self.rag.use_chroma and self.rag.collection):
            return []

        own_chunks = self.rag.collection.get(
            where={"source": source_id}, include=["documents"]
        ).get("documents") or []
        if not own_chunks:
            return []

        results = self.rag.collection.query(
            query_texts=[own_chunks[0]],
            n_results=top_k + _RELATED_SEARCH_MARGIN,
            include=["metadatas"],
        )
        metadatas = (results.get("metadatas") or [[]])[0]

        seen: set[str] = set()
        related: list[str] = []
        for meta in metadatas:
            other = meta.get("source")
            if not other or other == source_id or other in seen:
                continue
            seen.add(other)
            related.append(other)
            if len(related) >= top_k:
                break
        return related

    def group_by_period(self) -> dict[str, list[str]]:
        """
        Regroupe les documents indexés par période détectée
        (`core/dates.py`, déjà calculée à l'indexation — voir
        `modules/rag_manager.add_text`) — un document couvrant plusieurs
        périodes apparaît dans chacun de ses groupes. « sans période »
        regroupe ce qui n'en a aucune identifiable.

        ⚠️ GRANULARITÉ — ANNÉE seule, jamais le mois. Validé en conditions
        réelles le 03/08/2026 sur la vraie collection de Cyril : 171
        groupes pour 39 documents (voir ROADMAP.md §5.8), parce que
        `core/dates.extract_periods()` ajoute TOUJOURS le mois ET l'année
        pour une même date trouvée (« 2025-07 » et « 2025 » à la fois —
        volontairement, pour le FILTRAGE de recherche RAG, voir
        `RAG_MAX_DISTANCE_DATED`). Un document qui mentionne beaucoup de
        dates réelles (relevé de carrière, CV) se retrouvait ainsi éclaté
        sur des dizaines de groupes mois+année quasi redondants pour un
        simple parcours par période. Filtrer sur l'année seule ramène la
        même collection à 40 groupes — un par document, plus les années
        partagées entre plusieurs documents. Ne touche ni `core/dates.py`
        ni l'indexation (`rag_manager.add_text`) : la précision mois reste
        entière pour la recherche datée, seul ce regroupement d'affichage
        change de niveau.

        Regroupement déterministe, pas une classification par sens/projet
        au sens plein de l'idée catalogue — voir l'en-tête du module.
        """
        if not (self.rag.use_chroma and self.rag.collection):
            return {}

        metadatas = self.rag.collection.get(include=["metadatas"]).get("metadatas") or []
        groups: dict[str, set[str]] = {}
        for meta in metadatas:
            source = meta.get("source")
            if not source:
                continue
            periods = meta.get("periods") or ""
            all_keys = periods.split(",") if periods else []
            keys = [key for key in all_keys if "-" not in key] or ["sans période"]
            for key in keys:
                groups.setdefault(key, set()).add(source)

        return {key: sorted(sources) for key, sources in sorted(groups.items())}
