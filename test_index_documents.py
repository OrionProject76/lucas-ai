# test_index_documents.py — indexation des documents personnels
#
# Aucun ChromaDB ni Ollama réels : la collection est remplacée par une
# fausse qui garde ses morceaux en mémoire. Ce qui est testé ici n'est
# pas le stockage — c'est l'IDEMPOTENCE, qui décide si relancer la
# commande est sans danger ou double silencieusement le contenu.

from __future__ import annotations

import pytest

from memory import index_documents
from memory.index_documents import index_directory
from modules.rag_manager import RAGManager


class _FakeCollection:
    """Collection ChromaDB en mémoire, avec filtrage par `source`."""

    def __init__(self) -> None:
        self.docs: dict[str, tuple[str, dict]] = {}

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

    def delete(self, ids):
        for i in ids:
            self.docs.pop(i, None)


@pytest.fixture
def rag(monkeypatch):
    instance = RAGManager.__new__(RAGManager)
    instance.documents = []
    instance.chunks = []
    instance.use_chroma = True
    instance.collection = _FakeCollection()
    monkeypatch.setattr(index_documents, "RAGManager", lambda *a, **k: instance)
    return instance


@pytest.fixture
def dossier(tmp_path):
    (tmp_path / "conges.txt").write_text(
        "Politique de conges.\n\nChaque salarie acquiert 2,08 jours par mois.",
        encoding="utf-8",
    )
    (tmp_path / "assurance.md").write_text(
        "# Contrat 4471-B\n\nLa franchise s'eleve a 150 euros par sinistre.",
        encoding="utf-8",
    )
    return tmp_path


# ── Idempotence : la propriété qui compte ─────────────────────────────

def test_relancer_ne_double_pas_le_contenu(rag, dossier, capsys):
    """
    Sans ça, chaque exécution empilait des doublons et la recherche
    remontait deux fois le même extrait.
    """
    index_directory(dossier)
    apres_un = dict(rag.collection.docs)

    index_directory(dossier)

    assert rag.collection.docs == apres_un
    assert "inchangé" in capsys.readouterr().out


def test_un_fichier_modifie_remplace_ses_morceaux(rag, dossier):
    index_directory(dossier)
    (dossier / "conges.txt").write_text(
        "Politique revisee.\n\nDesormais 30 jours ouvres par an.", encoding="utf-8"
    )
    index_directory(dossier)

    morceaux = [d for d, m in rag.collection.docs.values() if m["source"] == "conges.txt"]
    assert any("30 jours" in m for m in morceaux)
    assert not any("2,08" in m for m in morceaux), "ancien contenu toujours consultable"


def test_un_fichier_supprime_est_retire_de_la_base(rag, dossier):
    """
    Un document effacé du disque resterait sinon consultable
    indéfiniment : la base n'a aucun moyen de l'apprendre autrement.
    """
    index_directory(dossier)
    (dossier / "conges.txt").unlink()
    index_directory(dossier)

    assert "conges.txt" not in rag.indexed_documents()
    assert "assurance.md" in rag.indexed_documents()


def test_reset_vide_la_base(rag, dossier):
    index_directory(dossier)
    (dossier / "conges.txt").unlink()
    (dossier / "assurance.md").unlink()

    index_directory(dossier, reset=True)
    assert rag.indexed_documents() == set()


# ── Ce qui est lu, ce qui ne l'est pas ────────────────────────────────

def test_le_readme_du_dossier_n_est_pas_un_document(rag, dossier):
    """
    Indexé, il répondrait à « comment j'indexe mes documents ? » par
    lui-même — la même pollution que l'ancien sample_document.txt.
    """
    (dossier / "README.md").write_text("Depose ici tes documents.", encoding="utf-8")
    index_directory(dossier)

    assert "README.md" not in rag.indexed_documents()


def test_les_formats_non_geres_sont_signales(rag, dossier, capsys):
    """
    Ignorés en silence, un .docx déposé qui n'apparaît jamais dans les
    réponses serait incompréhensible du point de vue de Cyril.
    """
    (dossier / "rapport.docx").write_bytes(b"PK faux docx")
    index_directory(dossier)

    sortie = capsys.readouterr().out
    assert "rapport.docx" in sortie
    assert "python-docx" in sortie


# ── PDF ───────────────────────────────────────────────────────────────
#
# pypdf est installé depuis le 01/08/2026 : les contrats et relevés de
# Cyril sont dans ce format. Aucun PDF réel n'est lu ici — c'est le
# COMPORTEMENT face aux trois cas qui compte, et deux d'entre eux
# (scanné, corrompu) sont ceux qu'on rencontre vraiment.

def _fake_pypdf(monkeypatch, pages, encrypted=False, boom=None):
    """Remplace pypdf.PdfReader par une doublure."""
    import sys
    import types

    class _Page:
        def __init__(self, texte):
            self._texte = texte

        def extract_text(self):
            return self._texte

    class _Reader:
        def __init__(self, path):
            if boom:
                raise boom
            self.is_encrypted = encrypted
            self.pages = [_Page(p) for p in pages]

        def decrypt(self, password):
            raise ValueError("mot de passe requis")

    module = types.ModuleType("pypdf")
    module.PdfReader = _Reader
    monkeypatch.setitem(sys.modules, "pypdf", module)


def test_un_pdf_avec_texte_est_indexe(rag, dossier, monkeypatch):
    _fake_pypdf(monkeypatch, ["La franchise s'eleve a 150 euros par sinistre declare. " * 3])
    (dossier / "contrat.pdf").write_bytes(b"%PDF-1.4")
    index_directory(dossier)

    assert "contrat.pdf" in rag.indexed_documents()


def test_un_pdf_scanne_est_signale_comme_tel(rag, dossier, monkeypatch, capsys):
    """
    LE cas courant : un contrat reçu par la poste et photographié n'a
    aucune couche texte. « document vide » ne dirait pas quoi faire ;
    « probablement scanné » dit que seul un OCR le rendrait consultable.
    """
    _fake_pypdf(monkeypatch, ["", "  "])
    (dossier / "scan.pdf").write_bytes(b"%PDF-1.4")
    index_directory(dossier)

    sortie = capsys.readouterr().out
    assert "scan.pdf" in sortie
    assert "scanné" in sortie
    assert "scan.pdf" not in rag.indexed_documents()


def test_un_pdf_corrompu_n_interrompt_pas_les_autres(rag, dossier, monkeypatch):
    from pypdf.errors import PdfStreamError

    _fake_pypdf(monkeypatch, [], boom=PdfStreamError("flux illisible"))
    (dossier / "casse.pdf").write_bytes(b"%PDF-1.4 faux")
    index_directory(dossier)

    assert "casse.pdf" not in rag.indexed_documents()
    assert "assurance.md" in rag.indexed_documents()


def test_un_pdf_chiffre_est_signale(rag, dossier, monkeypatch, capsys):
    _fake_pypdf(monkeypatch, ["du texte"], encrypted=True)
    (dossier / "protege.pdf").write_bytes(b"%PDF-1.4")
    index_directory(dossier)

    assert "chiffré" in capsys.readouterr().out


def test_pypdf_absent_ne_casse_pas_l_indexation(rag, dossier, monkeypatch, capsys):
    """
    La dépendance peut manquer sur une autre machine : le module doit
    rester utilisable, en signalant quoi installer.
    """
    import sys

    monkeypatch.setitem(sys.modules, "pypdf", None)
    (dossier / "contrat.pdf").write_bytes(b"%PDF-1.4")
    index_directory(dossier)

    assert "pip install pypdf" in capsys.readouterr().out
    assert "assurance.md" in rag.indexed_documents()


def test_un_fichier_illisible_n_interrompt_pas_les_autres(rag, dossier):
    (dossier / "casse.txt").write_bytes(b"\xff\xfe\x00\x00 binaire \xc3\x28")
    index_directory(dossier)

    assert "assurance.md" in rag.indexed_documents()
    assert "conges.txt" in rag.indexed_documents()


def test_un_dossier_absent_ne_leve_pas(rag, tmp_path):
    assert index_directory(tmp_path / "nexiste_pas") == 1


def test_un_document_vide_est_ignore(rag, dossier):
    (dossier / "vide.txt").write_text("   \n\n  ", encoding="utf-8")
    index_directory(dossier)
    assert "vide.txt" not in rag.indexed_documents()


# ── Découpage ─────────────────────────────────────────────────────────

def test_le_decoupage_respecte_les_paragraphes():
    """
    L'ancienne version coupait tous les 500 caractères sans regarder le
    contenu. Un extrait qui commence par « ...ent de 1 250 euros » perd
    de quoi il parle, et son embedding avec.
    """
    rag = RAGManager.__new__(RAGManager)
    texte = "\n\n".join(f"Paragraphe numero {i} avec du contenu." for i in range(20))
    morceaux = rag._chunk_text(texte, chunk_size=200, overlap=0)

    assert len(morceaux) > 1
    for m in morceaux:
        assert m.strip().startswith("Paragraphe"), f"coupé en plein milieu : {m[:40]!r}"


def test_un_paragraphe_trop_long_est_bien_coupe():
    """Faute de mieux — mais il ne doit pas disparaître ni tout déborder."""
    rag = RAGManager.__new__(RAGManager)
    morceaux = rag._chunk_text("x" * 2000, chunk_size=500, overlap=0)

    assert len(morceaux) == 4
    assert sum(len(m) for m in morceaux) == 2000


def test_le_recouvrement_relie_les_morceaux():
    """
    Une réponse à cheval sur deux paragraphes serait sinon coupée en deux
    moitiés dont aucune ne suffit à répondre.
    """
    rag = RAGManager.__new__(RAGManager)
    texte = "\n\n".join(f"Paragraphe {i} " + "mot " * 20 for i in range(6))

    sans = rag._chunk_text(texte, chunk_size=300, overlap=0)
    avec = rag._chunk_text(texte, chunk_size=300, overlap=100)

    assert sum(len(m) for m in avec) > sum(len(m) for m in sans)


# ── Sécurité ──────────────────────────────────────────────────────────

def test_aucun_appel_sortant(rag):
    """
    Contrats, relevés, notes personnelles. Les embeddings sont calculés
    par Ollama en local ; rien ne doit partir ailleurs (CLAUDE.md règle 3).
    """
    import inspect

    source = inspect.getsource(index_documents)
    for interdit in ("requests.", "urllib", "http://", "https://", "openai"):
        assert interdit not in source


def test_le_contenu_des_documents_n_est_jamais_affiche(rag, dossier, capsys):
    """
    La commande doit pouvoir tourner devant quelqu'un : noms de fichiers
    et compteurs, jamais le texte des documents.
    """
    (dossier / "secret.txt").write_text(
        "Mon IBAN est FR76 3000 1000 0100 0000 0000 123", encoding="utf-8"
    )
    index_directory(dossier)

    sortie = capsys.readouterr().out
    assert "secret.txt" in sortie
    assert "IBAN" not in sortie
    assert "FR76" not in sortie


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
