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

import math
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
            "documents d'abord :\n"
            "  1. les déposer dans data/documents/\n"
            "  2. venv\\Scripts\\python.exe -m memory.index_documents"
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

    # ── Choix du seuil ────────────────────────────────────────────────
    #
    # ⚠️ Ne PAS se contenter de min/max. Sur un corpus réel les deux
    # populations se chevauchent presque toujours un peu, et une seule
    # question pertinente mal formulée suffit alors à bloquer la mesure —
    # mesuré : 39 pertinents sur 40 sous le meilleur hors-sujet, et le
    # 40e faisait échouer tout le calibrage.
    #
    # Ce qui compte n'est pas une séparation parfaite mais le COMPROMIS :
    # combien d'extraits utiles on garde, combien de hors-sujet on
    # bloque. Le hors-sujet pèse plus lourd — c'est lui qui a noyé le
    # bloc vision et fait répondre à côté.
    relevant_values = [d for d, _ in relevant]
    irrelevant_values = [d for d, _ in irrelevant]

    def score(threshold: float) -> tuple[float, float]:
        gardes = sum(d <= threshold for d in relevant_values) / len(relevant_values)
        bloques = sum(d > threshold for d in irrelevant_values) / len(irrelevant_values)
        return gardes, bloques

    candidats = sorted({round(d, 3) for d in relevant_values + irrelevant_values})
    # Un hors-sujet qui passe coûte deux fois un extrait utile perdu.
    best = max(candidats, key=lambda t: (score(t)[0] + 2 * score(t)[1], -t))
    gardes, bloques = score(best)

    print("\ncompromis selon le seuil :")
    for t in candidats:
        if t < best - 0.06 or t > best + 0.06:
            continue
        g, b = score(t)
        marque = "  <<<" if t == best else ""
        print(f"  {t:.3f}  garde {g:5.0%} des pertinents, bloque {b:5.0%} des hors-sujet{marque}")

    # ⚠️ Arrondi vers le BAS, jamais au plus proche. Mesuré : le meilleur
    # seuil valait 0,336 et le premier hors-sujet 0,341 — arrondir à 0,34
    # laissait un millième de marge, donc rien. Un arrondi qui rend le
    # seuil plus permissif que ce qu'on vient de mesurer annule la mesure.
    suggested = math.floor(best * 100) / 100
    print(
        f"\nseuil proposé : {suggested}"
        f"\n  garde {gardes:.0%} des extraits utiles"
        f"\n  bloque {bloques:.0%} des questions hors sujet"
        f"\nvaleur actuelle : {RAG_MAX_DISTANCE}"
    )

    if bloques < 1.0:
        rescapes = sorted(d for d in irrelevant_values if d <= best)
        print(
            f"\n⚠️  {len(rescapes)} question(s) hors sujet passe(nt) encore ce seuil "
            f"({', '.join(f'{d:.3f}' for d in rescapes)}).\n"
            "    Le RAG injectera parfois un extrait sans rapport. Le premier\n"
            "    filtre reste core/intent.py, qui empêche la plupart de ces\n"
            "    questions d'atteindre le RAG."
        )
    if gardes < 0.9:
        print(
            f"\n⚠️  {1 - gardes:.0%} des extraits utiles sont écartés : Luca's\n"
            "    répondra « je ne trouve rien » sur des questions légitimes."
        )

    print(f"\nÀ reporter dans config.py :\n    RAG_MAX_DISTANCE: float = {suggested}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
