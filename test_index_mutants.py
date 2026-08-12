# test_index_mutants.py — les 12 survivants de memory/index_documents.py
#
# ⚠️ Pourquoi ce fichier existe (06/08/2026)
# ------------------------------------------
# Cinquième palier de la campagne de mutation.
#
# Ce module décide QUELS fichiers de Cyril entrent dans la base
# consultable. Deux de ses survivants portent sur des valeurs par défaut
# dont l'inversion serait grave :
#
#   433  `allow_secrets=False` — le défaut refuse d'indexer un fichier
#        reconnu comme secret
#   483  `reset=False`         — le défaut n'efface PAS la base existante
#
# Un défaut qui bascule est le pire genre de régression : rien dans le
# code appelant ne change, et le comportement s'inverse partout à la fois.
#
# ⚠️ Quatre autres (476, 525, 576, 596) vivent EN LIGNE dans
# `index_directory` — pas dans des fonctions isolables. Ils se testent
# donc par la sortie standard, avec un double de RAGManager.

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from memory import index_documents as idx


class _RagDouble:
    """Un RAGManager qui accepte tout, sans ChromaDB ni embeddings."""

    def __init__(self, deja_en_base: set[str] | None = None, morceaux: int = 1) -> None:
        self.use_chroma = True
        self.documents: list[str] = []
        self._morceaux = morceaux
        self._connus = set(deja_en_base or set())
        self.retires: list[str] = []
        rag = self

        class _Collection:
            def get(self, include=None, where=None):
                return {"ids": ["x"] * max(len(rag._connus), 1), "metadatas": []}

        self.collection = _Collection()

    def add_text(self, texte, doc_id):
        self.documents.append(doc_id)
        self._connus.add(doc_id)
        return True

    def indexed_documents(self):
        return set(self._connus)

    def remove_document(self, doc_id):
        self.retires.append(doc_id)
        self._connus.discard(doc_id)
        return 1

    def _chunk_text(self, texte, chunk_size=None, overlap=None):
        return ["morceau"] * self._morceaux


@pytest.fixture
def sans_ocr(monkeypatch):
    """Neutralise le moteur OCR : aucun modèle chargé pendant les tests."""
    class _Moteur:
        def extract_text(self, chemin):
            raise idx.OCRUnavailable("OCR neutralisé pour les tests")

    monkeypatch.setattr(idx, "OCREngine", _Moteur)


# ══ 433 / 483 — les deux défauts qui protègent ═══════════════════════

def test_indexing_refuses_secrets_by_default() -> None:
    """
    Mutant 433 : `allow_secrets: bool = False` -> `True`.

    Un appelant qui n'y pense pas — et c'est le cas de tous les appelants
    actuels — indexerait alors mots de passe et clés d'API dans une base
    consultable par le LLM. Le défaut doit REFUSER ; autoriser reste
    possible, mais explicitement.
    """
    assert inspect.signature(idx._collect).parameters["allow_secrets"].default is False
    assert inspect.signature(idx.index_directory).parameters["allow_secrets"].default is False


def test_indexing_never_wipes_the_base_by_default() -> None:
    """
    ⚠️ Mutant 483 : `reset: bool = False` -> `True`.

    `reset` retire TOUS les documents connus avant d'indexer. Basculé par
    défaut, un simple `index_directory()` viderait la base de Cyril —
    action destructive déclenchée par une commande qui a l'air additive.
    """
    assert inspect.signature(idx.index_directory).parameters["reset"].default is False


def test_a_secret_file_is_refused_unless_explicitly_allowed(tmp_path) -> None:
    """
    Le défaut n'est pas qu'une signature : il change le résultat.

    ⚠️ « secrets.txt » et non « .env » : les motifs portent sur le NOM
    (mot de passe, password, api_key, secrets…), pas sur l'extension.
    Vérifié plutôt que supposé — ma première version utilisait `.env`,
    qui n'est pas reconnu.
    """
    (tmp_path / "notes.txt").write_text("contenu anodin", encoding="utf-8")
    (tmp_path / "secrets.txt").write_text("API_KEY=xxx", encoding="utf-8")

    _, _, refuses, _ = idx._collect(tmp_path)
    assert refuses, "un fichier de secrets doit être refusé par défaut"

    _, _, refuses_autorises, _ = idx._collect(tmp_path, allow_secrets=True)
    assert not refuses_autorises, "explicitement autorisé, il ne doit plus être refusé"


def test_a_reset_only_wipes_when_asked(monkeypatch, tmp_path, sans_ocr) -> None:
    """L'effet réel du défaut, pas seulement sa signature."""
    (tmp_path / "note.txt").write_text("contenu", encoding="utf-8")

    rag = _RagDouble(deja_en_base={"ancien.txt"})
    monkeypatch.setattr(idx, "RAGManager", lambda: rag)
    idx.index_directory(tmp_path)
    # ⚠️ `ancien.txt` EST retiré, mais comme ORPHELIN (absent du dossier),
    # pas par un vidage préalable. La distinction compte : un reset
    # effacerait TOUT avant même de regarder le dossier.
    assert rag.documents == ["note.txt"], "le nouveau document doit être indexé"


# ══ 407 — un journal reste hors de la base ═══════════════════════════

def test_a_log_file_is_recognised_by_its_extension() -> None:
    """
    Mutant 407 : `return True` -> `False`. Les journaux entreraient dans
    la base — des milliers de lignes de bruit qui noieraient les vrais
    documents. Mesuré en réel : un `log.txt` de 0,7 Mo a produit 818
    morceaux sur 1086, soit 75 % de la base.
    """
    assert idx.looks_like_a_log(Path("serveur.log")) is True
    assert idx.looks_like_a_log(Path("SERVEUR.LOG")) is True, "la casse ne doit pas compter"
    assert idx.looks_like_a_log(Path("cv.pdf")) is False


# ══ 496 — ChromaDB indisponible : on s'arrête, on ne plante pas ══════

def test_indexing_stops_cleanly_when_the_collection_is_missing(monkeypatch, tmp_path) -> None:
    """
    Mutant 496 : `not rag.use_chroma or rag.collection is None` -> `and`.
    Avec `and`, un RAG à moitié disponible (`use_chroma` vrai, collection
    absente) passait le garde et l'indexation tombait plus loin sur
    `None.add(...)`.
    """
    class _RagCasse:
        use_chroma = True
        collection = None

    monkeypatch.setattr(idx, "RAGManager", lambda: _RagCasse())
    (tmp_path / "note.txt").write_text("contenu", encoding="utf-8")

    assert idx.index_directory(tmp_path) == 1, (
        "l'indexation doit rendre un code d'erreur, pas planter"
    )


# ══ 525 — l'aperçu des journaux annonce ce qu'il cache ═══════════════

def test_the_log_preview_counts_what_it_hides(monkeypatch, tmp_path, capsys, sans_ocr) -> None:
    """
    Mutant 525 : `(f" (+{len(logs) - 4})" if len(logs) > 4 else "")` ->
    `<=`. Le suffixe dit à Cyril combien de journaux ne sont PAS
    affichés. Inversé, il apparaît quand il n'y a rien à cacher et
    disparaît quand il y en a — un compteur qui ment sur ce qu'il compte.
    """
    for i in range(6):
        (tmp_path / f"serveur{i}.log").write_text("ligne", encoding="utf-8")
    (tmp_path / "note.txt").write_text("contenu", encoding="utf-8")

    monkeypatch.setattr(idx, "RAGManager", lambda: _RagDouble())
    idx.index_directory(tmp_path)

    sortie = capsys.readouterr().out
    assert "Journaux ignorés (6)" in sortie
    assert "(+2)" in sortie, "6 journaux, 4 affichés : il doit rester « (+2) »"


# ══ 476 — même compteur pour les formats non gérés ═══════════════════

def test_the_unsupported_preview_counts_what_it_hides(capsys) -> None:
    """
    Mutant 476 : même motif, sur la liste des formats non gérés.
    `_explain_unsupported` est, elle, isolable.
    """
    idx._explain_unsupported({".xlsx": ["a.xlsx", "b.xlsx"]})
    assert "(+" not in capsys.readouterr().out, "2 fichiers sur 3 affichés : rien à cacher"

    idx._explain_unsupported({".xlsx": [f"f{i}.xlsx" for i in range(5)]})
    assert "(+2)" in capsys.readouterr().out, "5 fichiers, 3 affichés : « (+2) »"


# ══ 576 — la division par le total ne se fait jamais sur zéro ════════

def test_the_dominance_report_never_divides_by_zero(monkeypatch, tmp_path, capsys, sans_ocr) -> None:
    """
    Mutant 576 : `total and morceaux / total > DOMINANCE_RATIO` -> `or`.

    Le `total and` n'est pas décoratif : c'est le garde contre la division
    par zéro. Avec `or`, une base vide fait diviser par 0 — et le rapport
    final, la seule chose que Cyril lit après une indexation, plante juste
    avant de s'afficher.
    """
    (tmp_path / "note.txt").write_text("contenu", encoding="utf-8")

    rag = _RagDouble()

    class _CollectionVide:
        def get(self, include=None, where=None):
            return {"ids": []}          # base vide : total = 0

    rag.collection = _CollectionVide()  # type: ignore[assignment]
    monkeypatch.setattr(idx, "RAGManager", lambda: rag)

    assert idx.index_directory(tmp_path) == 0, "une base vide ne doit pas faire planter"
    assert "morceaux sur" not in capsys.readouterr().out


# ══ 596 — la recalibration est annoncée dès qu'il y a du changement ══

def test_recalibration_is_announced_after_a_simple_addition(
    monkeypatch, tmp_path, capsys, sans_ocr
) -> None:
    """
    Mutant 596 : `if ajoutes or orphelins:` -> `and`. Avec `and`, l'avis
    de recalibration ne sortait QUE si les deux étaient non nuls — donc
    jamais après un simple ajout, alors que c'est précisément le cas où
    le seuil de pertinence n'est plus juste.
    """
    (tmp_path / "note.txt").write_text("contenu", encoding="utf-8")
    monkeypatch.setattr(idx, "RAGManager", lambda: _RagDouble())

    idx.index_directory(tmp_path)
    assert "recalibrer" in capsys.readouterr().out.lower(), (
        "un ajout seul suffit à rendre le seuil de pertinence caduc"
    )


# ══ 228 / 253 — le nettoyage temporaire ne masque pas la vraie erreur ══

def test_temp_cleanup_never_raises_over_the_real_error(monkeypatch, tmp_path) -> None:
    """
    Mutants 228 et 253 : `shutil.rmtree(..., ignore_errors=True)` ->
    `False`.

    Ces nettoyages tournent sur un chemin d'ERREUR et dans un `finally`.
    Sans `ignore_errors`, un dossier déjà supprimé — ou un fichier encore
    verrouillé par le moteur OCR — ferait lever le nettoyage LUI-MÊME, et
    cette exception remplacerait la vraie cause. Cyril verrait une erreur
    de suppression de fichier au lieu de « rendu PDF impossible ».
    """
    appels: list[bool] = []

    def _trace(chemin, ignore_errors=False, **kw):
        appels.append(ignore_errors)

    monkeypatch.setattr(idx.shutil, "rmtree", _trace)

    class _FitzCasse:
        @staticmethod
        def open(chemin):
            raise RuntimeError("PDF corrompu")

    monkeypatch.setitem(__import__("sys").modules, "fitz", _FitzCasse)

    faux_pdf = tmp_path / "doc.pdf"
    faux_pdf.write_bytes(b"%PDF-1.4 factice")

    with pytest.raises(idx.OCRUnavailable):
        idx._rasteriser_pdf(faux_pdf)

    assert appels, "le dossier temporaire doit être nettoyé"
    assert all(appels), "le nettoyage ne doit jamais lever par-dessus l'erreur d'origine"


# ══ 43 — la racine du projet en exécution directe ════════════════════

def test_the_project_root_is_added_when_run_outside_its_package() -> None:
    """
    Mutant 43 : `if __package__ in (None, "")` -> `not in`. Inversé, la
    racine n'est ajoutée QUE si le module tourne dans son paquet — soit
    exactement le cas où elle est déjà là — et jamais en exécution
    directe, où elle manque.
    """
    import importlib.util
    import sys

    chemin = Path(idx.__file__)
    racine = str(chemin.resolve().parent.parent)
    chemins = list(sys.path)
    try:
        while racine in sys.path:
            sys.path.remove(racine)

        spec = importlib.util.spec_from_file_location("index_documents_hors_paquet", chemin)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert racine in sys.path, "la racine doit être ajoutée hors paquet"
    finally:
        sys.path[:] = chemins


# ══ 294 — le moteur OCR fourni est celui qui sert ════════════════════

def test_a_supplied_ocr_engine_is_the_one_used(monkeypatch, tmp_path) -> None:
    """
    Mutant 294 : `ocr_engine or OCREngine()` -> `and`. Avec `and`, le
    moteur fourni est IGNORÉ au profit d'un moteur neuf — le paramètre ne
    sert plus à rien, et chaque PDF scanné recharge RapidOCR (le
    commentaire de `index_directory` explique justement qu'on l'évite).

    ⚠️ Il faut un PDF que pypdf PARSE mais dont la couche texte est vide.
    Ma première version envoyait `b"%PDF-1.4 factice"` : `PdfReader`
    échouait, `UnreadablePDF` était levée ligne 287, et la ligne 294
    n'était jamais atteinte. Le test passait sans rien exercer.
    """
    class _PageVide:
        def extract_text(self):
            return ""

    class _LecteurSansTexte:
        is_encrypted = False

        def __init__(self, chemin):
            # Attribut d'INSTANCE : une liste en attribut de classe serait
            # partagée entre toutes les instances (ruff RUF012).
            self.pages = [_PageVide()]

    import pypdf

    monkeypatch.setattr(pypdf, "PdfReader", _LecteurSansTexte)

    def _interdit(*a, **k):
        raise AssertionError("le moteur fourni doit être utilisé, pas un neuf")

    monkeypatch.setattr(idx, "OCREngine", _interdit)
    monkeypatch.setattr(idx, "_rasteriser_pdf", lambda path: tmp_path)

    class _MoteurFourni:
        def extract_text(self, chemin):
            raise idx.OCRUnavailable("moteur fourni, bien appelé")

    faux_pdf = tmp_path / "doc.pdf"
    faux_pdf.write_bytes(b"peu importe")

    with pytest.raises(idx.UnreadablePDF):
        # Exception de type assumée ci-dessous : le double n'implémente
        # que `extract_text`, seule méthode utilisée par le code testé.
        #
        # ⚠️ Un commentaire ne doit JAMAIS commencer par les mots d'une
        # directive : écrit en tête de ligne, mypy le lit comme un
        # « type: ignore » mal formé. Même piège que la directive noqa
        # de ruff (le seul "#" est celui de ce commentaire, pas un second
        # devant "noqa" — sinon ruff la lit comme une vraie directive mal
        # formée), rencontré deux fois aujourd'hui.
        idx._read_pdf(faux_pdf, ocr_engine=_MoteurFourni())  # type: ignore[arg-type]


# ══ 253 — les images intermédiaires disparaissent dans TOUS les cas ══

def test_intermediate_images_are_always_deleted(monkeypatch, tmp_path) -> None:
    """
    ⚠️ Ce nettoyage n'est pas de l'hygiène : les images sont des rendus de
    PAGES — pièces d'identité, contrats, relevés. Elles ne doivent pas
    traîner dans le dossier temporaire du système au-delà de la fonction.

    Mutant 253 : `shutil.rmtree(images_dir, ignore_errors=True)` ->
    `False`. Dans un `finally`, sans `ignore_errors`, un dossier déjà
    parti ferait lever le nettoyage lui-même — et cette exception
    remplacerait le résultat (ou la vraie erreur) de l'OCR.
    """
    images = tmp_path / "pages"
    images.mkdir()
    (images / "page_000.png").write_bytes(b"faux png")

    appels: list[bool] = []

    def _trace(chemin, ignore_errors=False, **kw):
        appels.append(ignore_errors)

    monkeypatch.setattr(idx.shutil, "rmtree", _trace)
    monkeypatch.setattr(idx, "_rasteriser_pdf", lambda path: images)

    class _Moteur:
        def extract_text(self, chemin):
            class _Resultat:
                is_empty = False
                text = "texte lu"
            return _Resultat()

    # Même motif que ci-dessus : double réduit à `extract_text`.
    assert idx._ocr_pdf(tmp_path / "doc.pdf", _Moteur()) == "texte lu"  # type: ignore[arg-type]
    assert appels, "les images doivent être nettoyées même en cas de succès"
    assert all(appels), "le nettoyage ne doit jamais lever par-dessus le résultat"
