# test_semantic_desktop.py — modules/semantic_desktop.py (lecture seule)
#
# Aucun ChromaDB ni Ollama réels : une fausse collection en mémoire,
# même famille que celle de test_index_documents.py, avec en plus
# .query() pour simuler la recherche par similarité.

from __future__ import annotations

import pytest

from modules.rag_manager import RAGManager
from modules.semantic_desktop import SemanticDesktop


class _FakeCollection:
    """Collection ChromaDB en mémoire — get() par source, query() par similarité déclarée."""

    def __init__(self) -> None:
        self.docs: dict[str, tuple[str, dict]] = {}
        # Ordre de similarité déclaré à l'avance par le test — évite de
        # simuler un vrai calcul d'embeddings pour ce que ce module teste.
        self.query_order: list[str] = []

    def add(self, documents, metadatas, ids):
        for doc, meta, id_ in zip(documents, metadatas, ids):
            self.docs[id_] = (doc, meta)

    def get(self, where=None, include=None):
        items = [
            (i, doc, meta) for i, (doc, meta) in self.docs.items()
            if not where or meta.get("source") == where["source"]
        ]
        return {
            "ids": [i for i, _, _ in items],
            "documents": [d for _, d, _ in items],
            "metadatas": [m for _, _, m in items],
        }

    def query(self, query_texts, n_results, include=None):
        ordered = self.query_order[:n_results] or list(self.docs.keys())[:n_results]
        metadatas = [self.docs[i][1] for i in ordered if i in self.docs]
        return {"metadatas": [metadatas]}


@pytest.fixture
def desktop() -> tuple[SemanticDesktop, _FakeCollection]:
    rag = RAGManager.__new__(RAGManager)
    rag.documents = []
    rag.chunks = []
    rag.use_chroma = True
    rag.collection = _FakeCollection()
    return SemanticDesktop(rag), rag.collection


def _index(collection: _FakeCollection, source: str, chunks: list[str], periods: str = "") -> None:
    for i, chunk in enumerate(chunks):
        collection.add(
            documents=[chunk],
            metadatas=[{"source": source, "chunk": i, "periods": periods}],
            ids=[f"{source}_{i}"],
        )


def test_list_documents_is_sorted(desktop) -> None:
    sd, collection = desktop
    _index(collection, "zebre.pdf", ["contenu"])
    _index(collection, "alpha.pdf", ["contenu"])

    assert sd.list_documents() == ["alpha.pdf", "zebre.pdf"]


def test_related_documents_excludes_the_source_itself(desktop) -> None:
    sd, collection = desktop
    _index(collection, "cv.pdf", ["Curriculum vitae de Cyril"])
    _index(collection, "lettre.pdf", ["Lettre de motivation"])
    collection.query_order = ["cv.pdf_0", "lettre.pdf_0"]

    related = sd.related_documents("cv.pdf", top_k=3)

    assert related == ["lettre.pdf"]


def test_related_documents_deduplicates_by_source(desktop) -> None:
    """Un même document apparu via plusieurs de ses morceaux ne doit sortir qu'une fois."""
    sd, collection = desktop
    _index(collection, "cv.pdf", ["Curriculum vitae de Cyril"])
    _index(collection, "lettre.pdf", ["Motivation, partie 1", "Motivation, partie 2"])
    _index(collection, "diplome.pdf", ["Diplôme obtenu en 2020"])
    collection.query_order = [
        "cv.pdf_0", "lettre.pdf_0", "lettre.pdf_1", "diplome.pdf_0",
    ]

    related = sd.related_documents("cv.pdf", top_k=5)

    assert related == ["lettre.pdf", "diplome.pdf"]


def test_related_documents_respects_top_k(desktop) -> None:
    sd, collection = desktop
    for name in ("a.pdf", "b.pdf", "c.pdf", "d.pdf"):
        _index(collection, name, ["contenu"])
    collection.query_order = ["a.pdf_0", "b.pdf_0", "c.pdf_0", "d.pdf_0"]

    related = sd.related_documents("a.pdf", top_k=2)

    assert related == ["b.pdf", "c.pdf"]


def test_related_documents_empty_when_source_not_indexed(desktop) -> None:
    sd, _ = desktop
    assert sd.related_documents("inconnu.pdf") == []


def test_related_documents_empty_without_chroma(desktop) -> None:
    sd, collection = desktop
    _index(collection, "cv.pdf", ["contenu"])
    sd.rag.use_chroma = False

    assert sd.related_documents("cv.pdf") == []


def test_group_by_period_groups_matching_documents(desktop) -> None:
    sd, collection = desktop
    _index(collection, "bulletin_juillet.pdf", ["contenu"], periods="2025-07,2025")
    _index(collection, "bulletin_aout.pdf", ["contenu"], periods="2025-08,2025")
    _index(collection, "cv.pdf", ["contenu"])  # aucune période

    groups = sd.group_by_period()

    assert groups["2025"] == ["bulletin_aout.pdf", "bulletin_juillet.pdf"]
    assert groups["sans période"] == ["cv.pdf"]


def test_group_by_period_handles_multiple_periods_per_document(desktop) -> None:
    """Un document qui couvre deux ANNÉES distinctes apparaît dans les deux groupes."""
    sd, collection = desktop
    _index(collection, "recap_annuel.pdf", ["contenu"], periods="2025-12,2025,2026-01,2026")

    groups = sd.group_by_period()

    assert groups["2025"] == ["recap_annuel.pdf"]
    assert groups["2026"] == ["recap_annuel.pdf"]


def test_group_by_period_ignores_month_level_granularity(desktop) -> None:
    """
    Régression du bug de granularité (ROADMAP.md §5.8) : 171 groupes pour
    39 documents réels, parce que core/dates.py ajoute toujours le mois
    ET l'année pour une même date. group_by_period() ne doit garder que
    l'année — aucune clé contenant "-" ne doit apparaître dans le résultat.
    """
    sd, collection = desktop
    _index(collection, "bulletin_juillet.pdf", ["contenu"], periods="2025-07,2025")

    groups = sd.group_by_period()

    assert "2025-07" not in groups
    assert groups["2025"] == ["bulletin_juillet.pdf"]


def test_group_by_period_empty_without_chroma(desktop) -> None:
    sd, collection = desktop
    _index(collection, "bulletin_juillet.pdf", ["contenu"], periods="2025-07,2025")
    sd.rag.use_chroma = False

    assert sd.group_by_period() == {}


def test_group_by_period_ignores_entries_without_a_source(desktop) -> None:
    """Une métadonnée sans "source" (chunk orphelin) ne doit pas produire de groupe fantôme."""
    sd, collection = desktop
    collection.add(documents=["contenu"], metadatas=[{"periods": "2025"}], ids=["orphelin_0"])
    _index(collection, "bulletin.pdf", ["contenu"], periods="2025")

    groups = sd.group_by_period()

    assert groups["2025"] == ["bulletin.pdf"]


def test_semantic_desktop_never_writes_to_disk() -> None:
    """
    Vérification statique : ce module ne doit importer aucun mécanisme
    d'écriture fichier (os.rename, shutil.move, Path.rename/unlink...).
    Lecture seule par conception (voir en-tête du module) — ce test
    échoue si quelqu'un y ajoute un jour une vraie action de fichier
    sans le décider explicitement ailleurs (Decision Engine).
    """
    import pathlib

    source = pathlib.Path("modules/semantic_desktop.py").read_text(encoding="utf-8")
    forbidden = ("shutil.move", "shutil.copy", ".rename(", ".unlink(", ".write_text(", ".write_bytes(")
    for pattern in forbidden:
        assert pattern not in source, f"écriture fichier détectée : {pattern}"
