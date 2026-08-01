# memory/index_documents.py — indexation des documents personnels
#
# ── À quoi ça sert ────────────────────────────────────────────────────
#
# Le RAG ne savait consulter que ce qu'on lui avait donné à la main, un
# fichier à la fois, depuis un interpréteur Python. Autant dire rien :
# la base ne contenait qu'un document d'exemple sur l'intelligence
# artificielle, qui polluait les réponses au lieu de les nourrir.
#
# Ce module lit un dossier et met la base à jour. Usage :
#
#     venv\Scripts\python.exe -m memory.index_documents
#     venv\Scripts\python.exe -m memory.index_documents --reset
#     venv\Scripts\python.exe -m memory.index_documents mes_docs/
#
# ── Ce qu'il garantit ─────────────────────────────────────────────────
#
# **Relancer la commande est sans danger.** Un fichier inchangé est
# ignoré (comparaison par empreinte du contenu), un fichier modifié voit
# ses anciens morceaux remplacés, et un fichier supprimé du disque est
# retiré de la base. Sans ça, chaque exécution empilait des doublons et
# la recherche remontait deux fois le même extrait.
#
# ── ⚠️ Sécurité ───────────────────────────────────────────────────────
#
# Ce sont les documents personnels de Cyril : contrats, relevés, notes.
# Rien ne sort de la machine — les embeddings sont calculés par Ollama en
# local (nomic-embed-text), et une question qui déclenche le RAG est
# forcée en local par route() (CLAUDE.md règle 3).
#
# Le CONTENU n'est jamais affiché ici, seulement les noms de fichiers et
# des compteurs : cette commande peut tourner devant quelqu'un.

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

if __package__ in (None, ""):  # exécution directe : python memory/index_documents.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DOCUMENTS_DIR  # noqa: E402
from modules.rag_manager import RAGManager  # noqa: E402

# Formats lus sans dépendance supplémentaire. Le PDF est volontairement
# absent : aucun lecteur n'est installé, et en ajouter un est une
# décision de dépendance, pas un détail — voir _explain_unsupported().
TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".rst", ".csv", ".json", ".log"}

# Signalés explicitement plutôt qu'ignorés en silence : un document
# déposé qui n'apparaît jamais dans les réponses est un bug incompréhensible
# du point de vue de Cyril.
# Le mode d'emploi du dossier n'est pas un document de Cyril. Indexé, il
# répondrait à « comment j'indexe mes documents ? » par lui-même, et
# polluerait les recherches comme le faisait sample_document.txt.
EXCLUDED_NAMES = {"readme.md", "readme.txt", "lisezmoi.txt"}

KNOWN_UNSUPPORTED = {
    ".pdf": "pip install pypdf",
    ".docx": "pip install python-docx",
    ".doc": "format ancien — réenregistrer en .docx ou .txt",
    ".odt": "réenregistrer en .txt",
    ".xlsx": "exporter en .csv",
}


def _read_text(path: Path) -> str | None:
    """
    Lit un fichier texte. Retourne None si l'encodage est illisible.

    Un seul fichier mal encodé ne doit pas interrompre l'indexation de
    tous les autres.
    """
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, LookupError):
            continue
        except OSError:
            return None
    return None


def _collect(directory: Path) -> tuple[list[Path], dict[str, list[str]]]:
    """Fichiers indexables, et fichiers reconnus mais non gérés."""
    indexable: list[Path] = []
    unsupported: dict[str, list[str]] = {}

    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.name.lower() in EXCLUDED_NAMES:
            continue
        suffix = path.suffix.lower()
        if suffix in TEXT_SUFFIXES:
            indexable.append(path)
        elif suffix in KNOWN_UNSUPPORTED:
            unsupported.setdefault(suffix, []).append(path.name)

    return indexable, unsupported


def _explain_unsupported(unsupported: dict[str, list[str]]) -> None:
    if not unsupported:
        return
    print("\nFormats non gérés pour l'instant :")
    for suffix, names in sorted(unsupported.items()):
        apercu = ", ".join(names[:3]) + (f" (+{len(names) - 3})" if len(names) > 3 else "")
        print(f"  {suffix:<7} {len(names):>3} fichier(s) — {KNOWN_UNSUPPORTED[suffix]}")
        print(f"          {apercu}")


def index_directory(directory: str | Path = DOCUMENTS_DIR, reset: bool = False) -> int:
    """
    Met la base à jour depuis un dossier. Retourne le code de sortie.
    """
    directory = Path(directory)
    if not directory.is_dir():
        print(f"Dossier introuvable : {directory}")
        print(f"Le créer et y déposer des documents, puis relancer.")
        return 1

    rag = RAGManager()
    if not rag.use_chroma or rag.collection is None:
        print("ChromaDB indisponible — indexation impossible.")
        print("Vérifier qu'Ollama tourne (ollama serve), il calcule les embeddings.")
        return 1

    if reset:
        connus = rag.indexed_documents()
        for doc_id in connus:
            rag.remove_document(doc_id)
        print(f"Base vidée : {len(connus)} document(s) retiré(s).\n")

    fichiers, non_geres = _collect(directory)
    if not fichiers:
        print(f"Aucun fichier indexable dans {directory}")
        print(f"Formats lus : {', '.join(sorted(TEXT_SUFFIXES))}")
        _explain_unsupported(non_geres)
        return 1

    print(f"{len(fichiers)} fichier(s) à examiner dans {directory}\n")

    ajoutes = inchanges = illisibles = 0
    vus: set[str] = set()

    for path in fichiers:
        doc_id = path.name
        vus.add(doc_id)

        texte = _read_text(path)
        if texte is None:
            print(f"  illisible  {doc_id}")
            illisibles += 1
            continue

        # add_text() rend False quand le contenu est identique à ce qui
        # est déjà en base — c'est ce qui rend la commande relançable.
        if rag.add_text(texte, doc_id):
            ajoutes += 1
        else:
            print(f"  inchangé   {doc_id}")
            inchanges += 1

    # Un fichier retiré du disque resterait consultable indéfiniment : la
    # base n'a aucun moyen de l'apprendre autrement qu'ici.
    orphelins = rag.indexed_documents() - vus
    for doc_id in sorted(orphelins):
        morceaux = rag.remove_document(doc_id)
        print(f"  retiré     {doc_id} ({morceaux} morceaux — absent du dossier)")

    total = len(rag.collection.get(include=[])["ids"])
    print(
        f"\n{ajoutes} indexé(s), {inchanges} inchangé(s), "
        f"{len(orphelins)} retiré(s), {illisibles} illisible(s)"
        f"\nbase : {total} morceaux"
    )
    _explain_unsupported(non_geres)

    # Le seuil de pertinence est calibré sur DEUX morceaux d'un document
    # d'exemple, avec une marge étroite (voir RAG_MAX_DISTANCE). Il n'a
    # plus aucune raison d'être juste maintenant que la base a changé.
    if ajoutes or orphelins:
        print(
            "\n➜ La base a changé : recalibrer le seuil de pertinence.\n"
            "  venv\\Scripts\\python.exe demos\\calibrate_rag.py"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Indexe les documents personnels pour le RAG (tout reste local).",
    )
    parser.add_argument(
        "directory", nargs="?", default=DOCUMENTS_DIR,
        help=f"dossier à indexer (défaut : {DOCUMENTS_DIR})",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="vide la base avant d'indexer (utile pour retirer les documents d'exemple)",
    )
    args = parser.parse_args(argv)
    return index_directory(args.directory, reset=args.reset)


if __name__ == "__main__":
    raise SystemExit(main())
