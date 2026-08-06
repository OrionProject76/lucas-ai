# test_rag_mutants.py — les 10 survivants de modules/rag_manager.py
#
# ⚠️ Pourquoi ce fichier existe (06/08/2026)
# ------------------------------------------
# Quatrième palier de la campagne de mutation.
#
# Le RAG lit les documents PERSONNELS de Cyril. Un survivant y coûte de
# deux façons : soit Luca's cesse de retrouver ce qu'elle devrait
# retrouver (et répond « je ne sais pas » sur un document qu'elle a),
# soit elle ré-indexe indéfiniment sans le dire.
#
# Quatre des dix portent le MÊME garde — `self.use_chroma and
# self.collection` — celui qui protège le mode dégradé. ChromaDB
# indisponible ne doit pas faire tomber Luca's : le RAG se coupe, le
# reste fonctionne (voir le commentaire de `RAGManager.__init__`).

from __future__ import annotations

import pytest

from modules.rag_manager import RAGManager


@pytest.fixture
def rag_degrade(monkeypatch, tmp_path) -> RAGManager:
    """Un RAGManager en mode dégradé : ChromaDB indisponible.

    ⚠️ `import chromadb` se fait DANS `__init__`, pas en tête de module :
    on ne peut donc pas monkeypatcher un attribut du module. Neutraliser
    l'entrée de `sys.modules` fait lever ImportError à cet import précis —
    exactement l'état d'une machine sans ChromaDB.
    """
    import sys

    monkeypatch.setitem(sys.modules, "chromadb", None)
    manager = RAGManager(data_dir=str(tmp_path))
    assert manager.use_chroma is False, "le repli doit s'être activé"
    assert manager.collection is None
    return manager


# ══ 171 / 179 / 296 / 358 — le garde du mode dégradé ══════════════════
#
# Mutant : `self.use_chroma and self.collection` -> `or`. Avec `or`, le
# chemin ChromaDB s'exécute alors que `collection` vaut None — chaque
# appel lève un AttributeError au lieu de dégrader proprement.

def test_removing_a_document_works_without_chromadb(rag_degrade) -> None:
    """Mutant 171."""
    rag_degrade.add_text("un contenu quelconque", "note.txt")
    assert rag_degrade.remove_document("note.txt") >= 0


def test_listing_documents_works_without_chromadb(rag_degrade) -> None:
    """Mutant 179."""
    rag_degrade.add_text("un contenu quelconque", "note.txt")
    assert "note.txt" in rag_degrade.indexed_documents()


def test_adding_a_document_works_without_chromadb(rag_degrade) -> None:
    """Mutant 296."""
    assert rag_degrade.add_text("le total est de 1847 euros", "releve.txt") is True


def test_searching_works_without_chromadb(rag_degrade) -> None:
    """Mutant 358."""
    rag_degrade.add_text("le total est de 1847 euros", "releve.txt")
    resultats = rag_degrade.search("total", top_k=3)
    assert isinstance(resultats, list)


# ══ 260 — un document vide n'est pas « ajouté » ═══════════════════════

def test_an_empty_document_reports_failure_not_success(rag_degrade) -> None:
    """
    Mutant 260 : `return False` -> `True`. Un document vide serait annoncé
    comme indexé — et Cyril croirait ses notes consultables alors que la
    base ne contient rien.
    """
    assert rag_degrade.add_text("   \n  ", "vide.txt") is False
    assert "vide.txt" not in rag_degrade.indexed_documents()


# ══ 327 — la liste des documents n'accumule pas de doublons ═══════════

def test_reindexing_the_same_document_does_not_duplicate_it(rag_degrade) -> None:
    """
    Mutant 327 : `if doc_id not in self.documents` -> `in`. Inversé, un
    document NEUF n'était jamais enregistré, et un document déjà connu
    l'était une fois de plus à chaque passage.
    """
    rag_degrade.add_text("version 1", "note.txt")
    rag_degrade.add_text("version 2 differente", "note.txt")

    assert rag_degrade.documents.count("note.txt") == 1, (
        "un document ré-indexé ne doit apparaître qu'une fois dans la liste"
    )


# ══ 217 — le découpage respecte la taille demandée ════════════════════

def test_two_paragraphs_that_fit_together_are_kept_in_one_chunk() -> None:
    """
    Mutant 217 : `len(current) + 2 + len(paragraph) <= chunk_size` -> `>`.

    ⚠️ Ce n'est PAS la taille finale qu'il faut mesurer : le recouvrement
    (`overlap`) fait volontairement dépasser certains morceaux, et ma
    première version l'a pris pour un défaut. Ce que la ligne décide,
    c'est la FUSION — deux paragraphes qui tiennent ensemble restent
    ensemble.

    Inversée, la fusion ne se produit que quand ça ne rentre PAS : deux
    paragraphes qui tiennent aisément sont séparés, et une réponse à
    cheval sur les deux se retrouve coupée en deux moitiés dont aucune ne
    suffit.
    """
    manager = RAGManager.__new__(RAGManager)
    # Deux paragraphes courts : 2 x 20 caractères + 2 de séparateur = 42,
    # très en dessous de la limite. Ils DOIVENT être fusionnés.
    morceaux = manager._chunk_text("premier paragraphe\n\nsecond paragraphe", chunk_size=200)

    assert len(morceaux) == 1, (
        f"deux paragraphes qui tiennent ensemble ne doivent pas être séparés : {morceaux}"
    )
    assert "premier" in morceaux[0] and "second" in morceaux[0]


# ══ 153 — un document inchangé n'est pas ré-indexé ════════════════════

def test_an_unchanged_document_is_recognised_as_already_indexed() -> None:
    """
    Mutant 153 : `existing.get("metadatas") or []` -> `and`. Avec `and`,
    la liste devient TOUJOURS vide, `_already_indexed` rend toujours
    False, et chaque document est ré-indexé à chaque passage — coût
    d'embedding inutile, et un journal qui annonce des ajouts qui n'en
    sont pas.
    """
    class _Collection:
        def get(self, where=None, include=None):
            return {"metadatas": [{"sha": "abc123"}, {"sha": "abc123"}]}

    manager = RAGManager.__new__(RAGManager)
    manager.collection = _Collection()  # type: ignore[assignment]

    assert manager._already_indexed("note.txt", "abc123") is True
    assert manager._already_indexed("note.txt", "autre_empreinte") is False


# ══ 298 — ré-indexer un document identique rend False ═════════════════

def test_reindexing_an_identical_document_reports_no_change() -> None:
    """
    Mutant 298 : `return False` -> `True`. Un document inchangé serait
    annoncé comme ré-indexé — Cyril croirait que sa modification a été
    prise en compte alors que rien n'a bougé.
    """
    class _Collection:
        def __init__(self):
            self.ajouts = 0

        def get(self, where=None, include=None):
            return {"metadatas": [{"sha": _EMPREINTE}]}

        def add(self, documents, metadatas, ids):
            self.ajouts += 1

        def delete(self, where=None):
            pass

    manager = RAGManager.__new__(RAGManager)
    manager.use_chroma = True
    collection = _Collection()
    manager.collection = collection  # type: ignore[assignment]
    manager.chunks = []
    manager.documents = []

    assert manager.add_text("contenu stable", "note.txt") is False
    assert collection.ajouts == 0, "rien ne doit être réécrit pour un document identique"


# Empreinte du document ci-dessus, calculée comme le fait le module.
def _calcule_empreinte() -> str:
    import hashlib

    # ⚠️ Deux détails à reproduire exactement, sinon le double ne
    # correspond à rien :
    #   • la version du FORMAT entre dans l'empreinte (voir le commentaire
    #     de `add_text`) — attribut de CLASSE `_FORMAT_VERSION` ;
    #   • l'empreinte est TRONQUÉE à 16 caractères.
    # Ma première version oubliait la troncature : `_already_indexed`
    # comparait un hash complet à un hash court, ne trouvait jamais
    # d'égalité, et le test échouait sans rapport avec ce qu'il visait.
    return hashlib.sha256(
        f"{RAGManager._FORMAT_VERSION}\ncontenu stable".encode()
    ).hexdigest()[:16]


_EMPREINTE = _calcule_empreinte()


# ══ L'état MIXTE : use_chroma vrai, mais collection absente ═══════════
#
# ⚠️ Pourquoi ces quatre tests s'ajoutent à ceux du mode dégradé.
#
# En mode dégradé, `use_chroma` ET `collection` sont tous deux faux : le
# garde `A and B` et sa mutation `A or B` se comportent alors à
# l'identique, et les quatre mutants survivaient malgré des tests verts.
#
# L'écart n'apparaît que dans l'état MIXTE — `use_chroma` vrai,
# `collection` à None. Il est atteignable : `__init__` pose
# `use_chroma = True` puis `collection = self._open_collection()`, et
# rien ne garantit que cette dernière rende toujours un objet.
#
# C'est précisément ce que le `and` protège : sans lui, chaque appel
# tomberait sur `None.get(...)` au lieu de dégrader.

@pytest.fixture
def rag_mixte(tmp_path) -> RAGManager:
    manager = RAGManager.__new__(RAGManager)
    manager.data_dir = str(tmp_path)
    manager.documents = []
    manager.chunks = []
    manager.use_chroma = True      # ChromaDB s'est bien importé…
    manager.collection = None      # …mais aucune collection n'a été ouverte
    return manager


def test_removing_a_document_degrades_when_the_collection_is_missing(rag_mixte) -> None:
    """Mutant 171 : `or` ferait appeler `None.delete(...)`."""
    assert rag_mixte.remove_document("note.txt") == 0


def test_listing_documents_degrades_when_the_collection_is_missing(rag_mixte) -> None:
    """Mutant 179 : `or` ferait appeler `None.get(...)`."""
    assert rag_mixte.indexed_documents() == set()


def test_adding_a_document_degrades_when_the_collection_is_missing(rag_mixte) -> None:
    """Mutant 296 : `or` ferait appeler `None.add(...)`."""
    assert rag_mixte.add_text("un contenu", "note.txt") is True
    assert "note.txt" in rag_mixte.documents


def test_searching_degrades_when_the_collection_is_missing(rag_mixte) -> None:
    """Mutant 358 : `or` ferait appeler `None.query(...)`."""
    rag_mixte.add_text("le total est de 1847 euros", "releve.txt")
    assert isinstance(rag_mixte.search("total"), list)


# ══ 499 — importer le module ne lance pas la démonstration ════════════

def test_importing_the_module_prints_nothing(capsys) -> None:
    """
    Mutant 499 : `if __name__ == "__main__"` -> `!=`. Inversé, le simple
    IMPORT exécute la démo : construction d'un RAGManager réel, lecture
    d'un fichier d'exemple, et un `print(get_context(...))`.

    ⚠️ Ma première version remplaçait `RAGManager` par une sentinelle
    avant de recharger — mais `reload()` RÉEXÉCUTE le module, donc
    redéfinit la classe avant d'atteindre le bloc. La sentinelle était
    écrasée et n'observait rien.

    La sortie standard, elle, survit au rechargement : c'est elle qu'on
    observe.
    """
    import importlib
    import sys

    capsys.readouterr()  # vide ce qui précède
    importlib.reload(sys.modules["modules.rag_manager"])
    sortie = capsys.readouterr()

    assert sortie.out.strip() == "", (
        f"l'import ne doit rien afficher — la démo s'est exécutée : {sortie.out[:200]!r}"
    )
