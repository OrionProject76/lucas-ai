# test_rag_manager.py — modules/rag_manager.py n'avait aucun fichier de
# test dédié (trouvé via mesure de couverture réelle, Priorité 3
# qualité/fiabilité, 04/08/2026). Portée initialement volontairement
# étroite : juste OllamaEmbeddingFunction.__call__().
#
# Complété le 04/08/2026 (nouvelle mesure de couverture, 65% -> le seul
# gros trou restant du projet) : RAGManager lui-même n'avait AUCUN test
# direct de __init__()/_open_collection() (toujours construit via
# RAGManager.__new__() ailleurs — test_index_documents.py,
# test_semantic_desktop.py, test_dates.py — qui court-circuite __init__
# et ne peut donc pas couvrir la connexion réelle à ChromaDB ni la
# migration L2 -> cosine), ni du chemin "use_chroma=False" (fallback
# sans ChromaDB) de remove_document()/indexed_documents()/add_text()/
# search(), ni de add_document() ou get_context() eux-mêmes. Le
# découpage (_chunk_text) et la recherche hybride par date (search(),
# chemin ChromaDB) étaient déjà bien couverts ailleurs — non dupliqués
# ici, sauf la branche "paragraphe en attente + paragraphe surdimensionné"
# qui manquait.

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from modules.rag_manager import OllamaEmbeddingFunction, RAGManager


class _FakeEmbeddingResponse:
    def __init__(self, embedding: list[float]) -> None:
        self._embedding = embedding

    def json(self):
        return {"embedding": self._embedding}


def test_embeds_a_single_text(monkeypatch) -> None:
    """
    ⚠️ chromadb enveloppe le retour de EmbeddingFunction.__call__ en
    numpy.ndarray (float32) — comparer via list()/round() plutôt que ==
    directement, sinon "truth value of an array is ambiguous".
    """
    monkeypatch.setattr(
        "modules.rag_manager.requests.post",
        lambda *a, **k: _FakeEmbeddingResponse([0.1, 0.2, 0.3]),
    )
    result = OllamaEmbeddingFunction()(["bonjour"])
    assert len(result) == 1
    assert [round(float(x), 1) for x in result[0]] == [0.1, 0.2, 0.3]


def test_embeds_each_text_separately_and_preserves_order(monkeypatch) -> None:
    calls: list[str] = []

    def _fake_post(url, json):
        calls.append(json["prompt"])
        return _FakeEmbeddingResponse([float(len(json["prompt"]))])

    monkeypatch.setattr("modules.rag_manager.requests.post", _fake_post)
    result = OllamaEmbeddingFunction()(["a", "bb", "ccc"])

    assert calls == ["a", "bb", "ccc"]
    assert [list(vec) for vec in result] == [[1.0], [2.0], [3.0]]


def test_calls_the_ollama_embeddings_endpoint_with_the_right_model(monkeypatch) -> None:
    from config import OLLAMA_HOST

    captured = {}

    def _fake_post(url, json):
        captured["url"] = url
        captured["model"] = json["model"]
        return _FakeEmbeddingResponse([0.0])

    monkeypatch.setattr("modules.rag_manager.requests.post", _fake_post)
    OllamaEmbeddingFunction()(["texte"])

    assert captured["url"] == f"{OLLAMA_HOST}/api/embeddings"
    assert captured["model"] == "nomic-embed-text"


def test_a_failed_embedding_call_raises_a_clear_french_error(monkeypatch) -> None:
    def _raise(*a, **k):
        raise ConnectionError("Ollama injoignable")

    monkeypatch.setattr("modules.rag_manager.requests.post", _raise)

    with pytest.raises(RuntimeError, match="ollama serve"):
        OllamaEmbeddingFunction()(["texte"])


def test_a_malformed_response_also_raises_a_clear_error(monkeypatch) -> None:
    """Une réponse sans la clé "embedding" ne doit jamais lever une KeyError brute."""
    class _BrokenResponse:
        def json(self):
            return {"unexpected": "shape"}

    monkeypatch.setattr(
        "modules.rag_manager.requests.post", lambda *a, **k: _BrokenResponse()
    )

    with pytest.raises(RuntimeError, match="Échec de l'embedding Ollama"):
        OllamaEmbeddingFunction()(["texte"])


# ── Découpage : la branche manquante ────────────────────────────────────

def test_chunk_text_flushes_the_pending_paragraph_before_an_oversized_one() -> None:
    """
    Un petit paragraphe accumulé dans `current`, suivi d'un paragraphe
    trop gros pour tenir : le premier doit être publié avant que le
    second soit débité en morceaux, pas perdu.
    """
    rag = RAGManager.__new__(RAGManager)
    texte = "Petit paragraphe.\n\n" + ("y" * 900)

    morceaux = rag._chunk_text(texte, chunk_size=500, overlap=0)

    assert morceaux[0] == "Petit paragraphe."
    assert morceaux[1:] == ["y" * 500, "y" * 400]


# ── __init__ / _open_collection : jamais construit réellement ──────────
#
# Tous les autres tests du projet passent par RAGManager.__new__(), qui
# court-circuite __init__ pour éviter d'avoir besoin d'un vrai ChromaDB —
# mais ça laisse __init__() et _open_collection() (bascule fallback,
# ouverture d'une collection existante, migration L2 -> cosine) sans
# aucun test. chromadb est injecté via sys.modules, comme _get_gpu_load()
# (GPUtil) et _get_active_window_title() (win32gui) dans world_model.py.

class _FakeChromaCollection:
    """Collection ChromaDB minimale pour les tests de _open_collection()."""

    def __init__(self, space, documents=None, metadatas=None, ids=None) -> None:
        self.metadata = {"hnsw:space": space}
        self._documents = documents or []
        self._metadatas = metadatas or []
        self._ids = ids or []
        self.added: dict | None = None

    def get(self, where=None, include=None):
        result: dict = {"ids": self._ids}
        if include and "documents" in include:
            result["documents"] = self._documents
        if include and "metadatas" in include:
            result["metadatas"] = self._metadatas
        return result

    def add(self, documents, metadatas, ids):
        self.added = {"documents": documents, "metadatas": metadatas, "ids": ids}


class _FakeChromaClient:
    """chroma_client factice : renvoie une collection connue, trace la migration."""

    def __init__(self, first_collection) -> None:
        self.first_collection = first_collection
        self.second_collection: _FakeChromaCollection | None = None
        self.deleted_collections: list[str] = []

    def get_or_create_collection(self, name, embedding_function, metadata):
        return self.first_collection

    def delete_collection(self, name) -> None:
        self.deleted_collections.append(name)

    def create_collection(self, name, embedding_function, metadata):
        self.second_collection = _FakeChromaCollection(space="cosine")
        return self.second_collection


def test_init_falls_back_when_chromadb_is_unavailable(monkeypatch, tmp_path) -> None:
    monkeypatch.setitem(sys.modules, "chromadb", None)

    rag = RAGManager(data_dir=str(tmp_path))

    assert rag.use_chroma is False
    assert rag.collection is None


def test_init_opens_an_existing_cosine_collection_without_migrating(monkeypatch, tmp_path) -> None:
    collection = _FakeChromaCollection(space="cosine")
    client = _FakeChromaClient(collection)
    monkeypatch.setitem(sys.modules, "chromadb", SimpleNamespace(PersistentClient=lambda path: client))

    rag = RAGManager(data_dir=str(tmp_path))

    assert rag.use_chroma is True
    assert rag.collection is collection
    assert client.deleted_collections == [], "déjà en cosine : aucune reconstruction nécessaire"


def test_init_migrates_an_old_l2_collection_with_existing_documents(monkeypatch, tmp_path) -> None:
    """
    ChromaDB fige l'espace de distance à la création : une collection L2
    historique doit être recréée en cosine, ses documents réinsérés.
    """
    old_collection = _FakeChromaCollection(
        space="l2",
        documents=["contenu a", "contenu b"],
        metadatas=[{"source": "a.txt"}, {"source": "b.txt"}],
        ids=["a.txt_0", "b.txt_0"],
    )
    client = _FakeChromaClient(old_collection)
    monkeypatch.setitem(sys.modules, "chromadb", SimpleNamespace(PersistentClient=lambda path: client))

    rag = RAGManager(data_dir=str(tmp_path))

    assert client.deleted_collections == ["orion_docs"]
    assert rag.collection is client.second_collection
    # `collection` est Optional : le dire ici plutot que de laisser un
    # AttributeError sur None si la reouverture echouait.
    assert rag.collection is not None
    assert rag.collection.added == {
        "documents": ["contenu a", "contenu b"],
        "metadatas": [{"source": "a.txt"}, {"source": "b.txt"}],
        "ids": ["a.txt_0", "b.txt_0"],
    }


def test_init_migrates_an_empty_l2_collection_without_reinserting(monkeypatch, tmp_path) -> None:
    old_collection = _FakeChromaCollection(space="l2")
    client = _FakeChromaClient(old_collection)
    monkeypatch.setitem(sys.modules, "chromadb", SimpleNamespace(PersistentClient=lambda path: client))

    rag = RAGManager(data_dir=str(tmp_path))

    assert client.deleted_collections == ["orion_docs"]
    assert rag.collection.added is None, "rien à réinsérer : la collection était vide"


# ── Mode fallback (use_chroma=False) ────────────────────────────────────
#
# Chemin emprunté quand ChromaDB est indisponible — jamais exercé jusqu'ici,
# tous les tests existants passent use_chroma=True avec une fausse collection.

def test_remove_document_without_chroma_removes_matching_chunks() -> None:
    rag = RAGManager.__new__(RAGManager)
    rag.use_chroma = False
    rag.collection = None
    rag.chunks = [("a.txt", 0, "contenu a"), ("b.txt", 0, "contenu b"), ("a.txt", 1, "suite a")]

    removed = rag.remove_document("a.txt")

    assert removed == 2
    assert rag.chunks == [("b.txt", 0, "contenu b")]


def test_indexed_documents_without_chroma_lists_chunk_doc_ids() -> None:
    rag = RAGManager.__new__(RAGManager)
    rag.use_chroma = False
    rag.collection = None
    rag.chunks = [("a.txt", 0, "x"), ("b.txt", 0, "y"), ("a.txt", 1, "z")]

    assert rag.indexed_documents() == {"a.txt", "b.txt"}


def test_add_text_without_chroma_replaces_previous_chunks_for_the_same_document() -> None:
    rag = RAGManager.__new__(RAGManager)
    rag.use_chroma = False
    rag.collection = None
    rag.chunks = []
    rag.documents = []

    rag.add_text("Premiere version.", "notes.txt")
    rag.add_text("Deuxieme version, plus longue et differente.", "notes.txt")

    ids = [doc_id for doc_id, _, _ in rag.chunks]
    assert ids.count("notes.txt") == 1, "l'ancienne version doit être remplacée, pas doublée"


def test_search_without_chroma_matches_substrings_case_insensitively() -> None:
    rag = RAGManager.__new__(RAGManager)
    rag.use_chroma = False
    rag.collection = None
    rag.chunks = [
        ("a.txt", 0, "Le contrat mentionne une FRANCHISE de 150 euros."),
        ("b.txt", 0, "Rien à voir ici."),
    ]

    assert rag.search("franchise", top_k=3) == ["Le contrat mentionne une FRANCHISE de 150 euros."]


# ── add_document() : jamais appelé directement ──────────────────────────
#
# memory/index_documents.py lit les fichiers lui-même et appelle add_text()
# directement (PDF, docx...) — add_document(), la façade "chemin -> texte",
# n'était donc jamais exercée par aucun test.

def test_add_document_reads_the_file_and_indexes_it(tmp_path) -> None:
    rag = RAGManager.__new__(RAGManager)
    rag.use_chroma = False
    rag.collection = None
    rag.chunks = []
    rag.documents = []

    fichier = tmp_path / "notes.txt"
    fichier.write_text("Contenu du fichier.", encoding="utf-8")

    assert rag.add_document(str(fichier)) is True
    assert any(doc_id == "notes.txt" for doc_id, _, _ in rag.chunks)


def test_add_document_reports_a_missing_file(capsys, tmp_path) -> None:
    rag = RAGManager.__new__(RAGManager)
    rag.use_chroma = False
    rag.collection = None
    rag.chunks = []
    rag.documents = []

    assert rag.add_document(str(tmp_path / "absent.txt")) is False
    assert "introuvable" in capsys.readouterr().out


# ── search() : le seuil désactivé ───────────────────────────────────────

class _FakeQueryCollection:
    """Collection dont query() renvoie une liste (document, distance, metadata) fixée."""

    def __init__(self, entries) -> None:
        self._entries = entries

    def count(self) -> int:
        return len(self._entries)

    def query(self, query_texts, n_results, include=None):
        retenus = self._entries[:n_results]
        return {
            "documents": [[doc for doc, _, _ in retenus]],
            "distances": [[dist for _, dist, _ in retenus]],
            "metadatas": [[meta for _, _, meta in retenus]],
        }


def test_search_with_max_distance_none_returns_everything_query_gave() -> None:
    """`max_distance=None` sert à diagnostiquer ce que la base contient réellement."""
    rag = RAGManager.__new__(RAGManager)
    rag.use_chroma = True
    rag.collection = _FakeQueryCollection([
        ("extrait pertinent", 0.10, {}),
        ("extrait lointain", 0.95, {}),
    ])

    resultats = rag.search("question quelconque", top_k=5, max_distance=None)

    assert resultats == ["extrait pertinent", "extrait lointain"]


# ── get_context() : jamais appelé directement ───────────────────────────
#
# core/lucas_core.py remplace toujours RAGManager en entier dans ses
# propres tests (test_vision_routing.py, test_router.py,
# test_memory_context.py) : get_context() lui-même n'était donc jamais
# exercé, pas même son chemin "aucun résultat".

def test_get_context_returns_empty_string_when_nothing_found() -> None:
    rag = RAGManager.__new__(RAGManager)
    rag.use_chroma = False
    rag.collection = None
    rag.chunks = []

    assert rag.get_context("question") == ""


def test_get_context_formats_the_found_extracts_and_truncates_them() -> None:
    rag = RAGManager.__new__(RAGManager)
    rag.use_chroma = False
    rag.collection = None
    rag.chunks = [("a.txt", 0, "x" * 400)]

    contexte = rag.get_context("x", top_k=3)

    assert contexte.startswith("Contexte trouvé dans les documents:")
    assert "[Extrait 1]" in contexte
    extrait = contexte.split("[Extrait 1] ", 1)[1]
    assert extrait.startswith("x" * 300 + "...")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
