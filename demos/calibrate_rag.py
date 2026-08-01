# demos/calibrate_rag.py — mesure le seuil de pertinence du RAG
#
# ── Pourquoi cet outil ────────────────────────────────────────────────
#
# RAG_MAX_DISTANCE (config.py) vaut 0.45, calibré sur DEUX chunks d'un
# document d'exemple, avec une marge étroite : 0,416 pour un extrait
# pertinent contre 0,449 pour un hors sujet. C'est trop peu pour tenir
# sur de vrais documents.
#
# Ce script refait la mesure automatiquement sur la base réellement
# indexée, au lieu de redemander une campagne de tests à la main.
#
# ── Comment il obtient des cas étiquetés sans étiquetage manuel ───────
#
# Il faut deux populations de distances : celles d'une question à
# laquelle la base PEUT répondre, et celles d'une question hors sujet.
#
#   • PERTINENT — pour chaque chunk indexé, le modèle local rédige une
#     question à laquelle ce chunk répond. La distance obtenue est par
#     construction celle d'une bonne correspondance.
#   • HORS SUJET — une liste fixe de questions sans rapport avec des
#     documents personnels (météo, calcul, culture générale).
#
# Le seuil se pose ensuite entre les deux populations. S'il n'existe
# aucune valeur qui les sépare, le script le DIT au lieu d'inventer un
# nombre : cela signifie que les documents indexés ressemblent trop aux
# questions témoins, et qu'il faut revoir les témoins, pas le seuil.
#
# Usage :
#     venv\Scripts\python.exe demos\calibrate_rag.py

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import RAG_MAX_DISTANCE  # noqa: E402
from core.local_llm import ask_local  # noqa: E402
from modules.rag_manager import RAGManager  # noqa: E402

# En dessous, la mesure ne veut rien dire : c'est le cas de la base
# actuelle (2 chunks d'un document d'exemple), celui qu'on cherche
# justement à dépasser.
MINIMUM_CHUNKS = 10

# Bornes du nombre de chunks sondés — au-delà, on paie une génération de
# question par chunk pour une précision qui ne bouge plus.
MAX_PROBES = 40

# Questions sans aucun rapport avec des documents personnels. Elles
# doivent rester loin de TOUT document indexé, quel que soit son sujet.
OFF_TOPIC = [
    "quelle heure il est",
    "combien font 17 fois 23",
    "explique-moi la photosynthèse",
    "raconte-moi une blague",
    "quel temps fait-il demain",
    "comment réparer un vélo",
    "merci, c'est parfait",
    "quelle est la capitale de l'Australie",
]

QUESTION_PROMPT = (
    "Voici un extrait d'un document. Écris UNE question courte, en français, "
    "à laquelle cet extrait répond. Réponds uniquement par la question, sans "
    "guillemets ni préambule.\n\nExtrait :\n"
)


def _closest_distance(collection, question: str) -> float | None:
    """Distance du meilleur extrait pour cette question."""
    result = collection.query(
        query_texts=[question], n_results=1, include=["distances"]
    )
    distances = (result.get("distances") or [[]])[0]
    return float(distances[0]) if distances else None


def _relevant_distances(collection, chunks: list[str]) -> list[tuple[float, str]]:
    """Une question par chunk, puis la distance qu'elle obtient."""
    measured = []
    for index, chunk in enumerate(chunks, start=1):
        question = ask_local(
            [{"role": "user", "content": QUESTION_PROMPT + chunk[:1200]}]
        ).strip()

        if question.startswith("[Erreur]"):
            print(f"  {index:>3}/{len(chunks)}  Ollama indisponible : {question}")
            return measured

        distance = _closest_distance(collection, question)
        if distance is None:
            continue
        measured.append((distance, question))
        print(f"  {index:>3}/{len(chunks)}  {distance:.3f}  {question[:58]}")
    return measured


def main() -> int:
    rag = RAGManager()
    if not rag.use_chroma or rag.collection is None:
        print("ChromaDB indisponible — rien à calibrer.")
        return 1

    stored = rag.collection.get(include=["documents"])
    chunks = [c for c in (stored.get("documents") or []) if c and c.strip()]

    print(f"Collection : {len(chunks)} chunks indexés.")
    if len(chunks) < MINIMUM_CHUNKS:
        print(
            f"\nMoins de {MINIMUM_CHUNKS} chunks : la mesure ne serait pas plus\n"
            "fiable que celle qui a donné la valeur actuelle. Indexe de vrais\n"
            "documents d'abord — RAGManager().add_document(chemin)."
        )
        return 1

    probes = chunks[:MAX_PROBES]
    if len(probes) < len(chunks):
        print(f"Sondage sur les {len(probes)} premiers chunks.\n")

    print("PERTINENT — une question rédigée depuis chaque extrait :")
    relevant = _relevant_distances(rag.collection, probes)

    print("\nHORS SUJET — questions sans rapport avec les documents :")
    irrelevant = []
    for question in OFF_TOPIC:
        distance = _closest_distance(rag.collection, question)
        if distance is None:
            continue
        irrelevant.append((distance, question))
        print(f"       {distance:.3f}  {question}")

    if not relevant or not irrelevant:
        print("\nPas assez de mesures exploitables.")
        return 1

    relevant.sort()
    irrelevant.sort()
    worst_relevant, worst_question = relevant[-1]
    best_irrelevant, best_question = irrelevant[0]

    print(
        f"\npertinent   : {relevant[0][0]:.3f} … {worst_relevant:.3f}"
        f"   ({len(relevant)} mesures)"
        f"\nhors sujet  : {best_irrelevant:.3f} … {irrelevant[-1][0]:.3f}"
        f"   ({len(irrelevant)} mesures)"
    )

    if worst_relevant >= best_irrelevant:
        # Cas honnête : aucune valeur ne sépare les deux populations.
        print(
            "\n⚠️  Les deux populations se CHEVAUCHENT — aucun seuil ne peut\n"
            "    les séparer. Ce n'est pas un réglage à trouver :\n"
            f"      pire cas pertinent  {worst_relevant:.3f}  « {worst_question[:50]} »\n"
            f"      meilleur hors sujet {best_irrelevant:.3f}  « {best_question}   »\n"
            "    Soit une question témoin touche vraiment un document indexé\n"
            "    (à retirer d'OFF_TOPIC), soit les documents sont trop\n"
            "    hétérogènes pour un seuil unique. Garder la valeur actuelle."
        )
        return 1

    suggested = round((worst_relevant + best_irrelevant) / 2, 2)
    margin = best_irrelevant - worst_relevant

    print(
        f"\nseuil proposé : {suggested}   (marge {margin:.3f})"
        f"\nvaleur actuelle : {RAG_MAX_DISTANCE}"
    )
    if margin < 0.05:
        print(
            "⚠️  Marge étroite : le seuil tiendra mal si de nouveaux documents\n"
            "    sont indexés. Relancer ce script après chaque ajout important."
        )

    print(f"\nÀ reporter dans config.py :\n    RAG_MAX_DISTANCE: float = {suggested}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
