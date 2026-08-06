# test_dates.py — reconnaissance des périodes, et recherche hybride
#
# ── Pourquoi ce fichier existe ────────────────────────────────────────
#
# Mesuré en conditions réelles via main.py : « Quel était mon salaire net
# en juillet 2025 ? » remontait les bulletins de février, avril et
# janvier 2026 — alors que celui de juillet 2025 est bien indexé. Pour un
# modèle d'embeddings, deux dates de bulletin de paie sont sémantiquement
# voisines : le mois demandé est exactement l'information qu'il écrase.
#
# Les noms de fichiers testés ici sont les VRAIS noms des documents de
# Cyril. C'est sur eux que la reconnaissance doit marcher, pas sur des
# formats choisis pour être commodes.

from __future__ import annotations

import pytest

from core.dates import extract_periods, extract_query_period
from core.dates import matches as matches_period
from test_memory_double import MemoryDouble

# ── Extraction côté documents ─────────────────────────────────────────

@pytest.mark.parametrize(
    "nom, attendu",
    [
        # JJMMAA — la période est dans le nom, le contenu du PDF de paie
        # étant souvent en morceaux illisibles.
        ("bulletin-de-paie-du-010725-au-310725.pdf", "2025-07"),
        ("bulletin-de-paie-du-011225-au-311225.pdf", "2025-12"),
        # MMAAAA
        ("bulletin-de-salaire-012026.pdf", "2026-01"),
        ("bulletin-de-salaire-032026.pdf", "2026-03"),
        # AAAAMM
        ("Facture_Free_202605_35291155_1471373504.pdf", "2026-05"),
        # JJ.MM.AAAA
        ("Attestation CALLOCH Cyril 07.04.2026.pdf", "2026-04"),
    ],
)
def test_les_vrais_noms_de_fichiers_livrent_leur_mois(nom: str, attendu: str) -> None:
    assert attendu in extract_periods(nom)


@pytest.mark.parametrize(
    "nom",
    [
        # ⚠️ L'année est COLLÉE à une lettre : \b n'y voit aucune
        # frontière de mot, et ces deux documents se retrouvaient sans
        # aucune date. Ce qu'il faut exclure, ce sont les chiffres
        # voisins, pas les lettres.
        "Relevé_de_Carrière2026.pdf",
        "Cv2026_DE-As.pdf",
    ],
)
def test_une_annee_collee_a_une_lettre_est_vue(nom: str) -> None:
    assert "2026" in extract_periods(nom)


def test_une_annee_sur_deux_chiffres_est_bornee_au_siecle_courant() -> None:
    """01/07/25 -> 2025, jamais 1925 (trou de couverture fermé le 04/08/2026)."""
    assert "2025-07" in extract_periods("releve du 01/07/25")


def test_les_mois_ecrits_en_toutes_lettres(self=None) -> None:
    assert "2025-07" in extract_periods("bulletin de juillet 2025")
    assert "2026-12" in extract_periods("versé en décembre 2026")
    # Sans accent ni majuscule : le texte est normalisé en amont.
    assert "2025-08" in extract_periods("AOUT 2025")


@pytest.mark.parametrize(
    "texte",
    [
        # ⚠️ Un numéro de sécurité sociale et un montant ne sont PAS des
        # dates. Sans bornes de vraisemblance, « 1 77 06 56 121 075 »
        # fournissait des années absurdes.
        "Numéro de Sécurité sociale : 1 77 06 56 121 075",
        "montant 1250,00 EUR reference 35291155",
        "code guichet 30001 compte 00010000000",
    ],
)
def test_les_nombres_qui_ne_sont_pas_des_dates(texte: str) -> None:
    assert extract_periods(texte) == set()


def test_un_horodatage_long_ne_livre_pas_son_heure() -> None:
    """
    « 20260408.120900 » : sans borne, le bloc « 120900 » de l'heure était
    lu comme le 12/09/00. Seuls les blocs isolés comptent — mais celui-ci
    l'est, entouré de points. On vérifie au moins que la partie AAAAMMJJ
    ne produit pas de période fantaisiste.
    """
    periodes = extract_periods("6620294369_ACOE9.20260408.120900.pdf")
    assert "2026-04" not in periodes or "2026" in periodes


# ── Extraction côté question ──────────────────────────────────────────

@pytest.mark.parametrize(
    "question, attendu",
    [
        ("Quel était mon salaire net en juillet 2025 ?", "2025-07"),
        ("ma paie du 01/07/2025", "2025-07"),
        ("mes bulletins de 2026", "2026"),
        ("combien j'ai gagné en décembre 2025", "2025-12"),
    ],
)
def test_la_question_livre_sa_periode(question: str, attendu: str) -> None:
    assert extract_query_period(question) == attendu


@pytest.mark.parametrize(
    "question",
    [
        "Résume-moi mon CV",
        "que dit mon relevé de carrière",
        "quelles sont mes garanties d'assurance",
    ],
)
def test_une_question_sans_date_ne_filtre_rien(question: str) -> None:
    """
    Filtrer sur une période que Cyril n'a pas demandée écarterait des
    documents pertinents. None signifie « ne filtre pas ».
    """
    assert extract_query_period(question) is None


def test_un_mois_sans_annee_ne_filtre_pas() -> None:
    """
    « combien j'ai gagné en mars » — quel mars ? Sur cinq ans de
    bulletins, se tromper d'année est aussi gênant que se tromper de
    mois. Mieux vaut ne pas filtrer et laisser le sémantique décider.
    """
    assert extract_query_period("combien j'ai gagné en mars") is None


# ── Correspondance ────────────────────────────────────────────────────

def test_un_mois_demande_est_strict() -> None:
    assert matches_period("2025-07", "2025,2025-07")
    assert not matches_period("2025-07", "2026,2026-02")
    assert not matches_period("2025-07", "2025,2025-08")


def test_une_annee_demandee_accepte_tous_ses_mois() -> None:
    """« mes bulletins de 2026 » doit retenir celui de janvier 2026."""
    assert matches_period("2026", "2026,2026-01")
    assert not matches_period("2026", "2025,2025-07")


def test_un_document_sans_periode_est_ecarte_par_un_filtre_de_date() -> None:
    assert not matches_period("2025-07", "")


# ── Recherche hybride ─────────────────────────────────────────────────

class _FakeCollection:
    """Collection qui rend les documents dans l'ordre fourni."""

    def __init__(self, entries):
        self.entries = entries          # [(texte, periods, distance)]
        self.derniere_demande = None
        self.total = len(entries)

    def count(self):
        return self.total

    def query(self, query_texts, n_results, include=None):
        self.derniere_demande = n_results
        retenus = self.entries[:n_results]
        return {
            "documents": [[t for t, _, _ in retenus]],
            "distances": [[d for _, _, d in retenus]],
            "metadatas": [[{"periods": p} for _, p, _ in retenus]],
        }


def _rag(entries):
    from modules.rag_manager import RAGManager

    instance = RAGManager.__new__(RAGManager)
    instance.use_chroma = True
    instance.chunks = []
    instance.collection = _FakeCollection(entries)
    return instance


def test_le_bon_mois_est_retenu_meme_loin_dans_le_classement():
    """
    LE cas réel. Le bulletin de juillet 2025 arrivait après ceux de 2026
    dans l'ordre sémantique — donc jamais dans le top 3.
    """
    rag = _rag([
        ("paie fevrier 2026", "2026,2026-02", 0.281),
        ("paie avril 2026", "2026,2026-04", 0.281),
        ("paie janvier 2026", "2026,2026-01", 0.283),
        ("paie juillet 2025", "2025,2025-07", 0.310),
    ])
    resultats = rag.search("Quel était mon salaire net en juillet 2025 ?", top_k=3)

    assert resultats == ["paie juillet 2025"]


def test_une_question_datee_interroge_toute_la_base():
    """
    ⚠️ Un premier essai élargissait ×10 — 30 candidats sur 275. Un seul
    morceau de juillet 2025 passait le filtre (celui des congés), et le
    morceau portant « NET SOCIAL 1625.68 » restait invisible alors qu'il
    est 2e parmi ceux de juillet. Le filtre par date est le critère
    principal ; le sémantique ne doit pas trancher avant lui.
    """
    rag = _rag([("paie juillet 2025", "2025,2025-07", 0.31)])
    rag.collection.total = 275
    rag.search("salaire de juillet 2025", top_k=3)

    assert rag.collection.derniere_demande == 275


def test_une_question_sans_date_ne_change_rien():
    rag = _rag([("mon cv", "2026", 0.28)])
    resultats = rag.search("Résume-moi mon CV", top_k=3)

    assert rag.collection.derniere_demande == 3
    assert resultats == ["mon cv"]


def test_aucun_document_pour_la_periode_ne_rend_RIEN():
    """
    ⚠️ Ne PAS se rabattre sur les meilleurs résultats sémantiques : ce
    serait exactement le bug d'origine, et Luca's répondrait sur un autre
    mois sans le dire. « Je n'ai rien pour juillet 2024 » vaut mieux
    qu'une réponse sur février 2026.
    """
    rag = _rag([
        ("paie fevrier 2026", "2026,2026-02", 0.28),
        ("paie avril 2026", "2026,2026-04", 0.28),
    ])
    assert rag.search("salaire de juillet 2024", top_k=3) == []


def test_le_seuil_de_pertinence_s_applique_toujours():
    """Le filtrage par date s'ajoute au seuil, il ne le remplace pas."""
    rag = _rag([("paie juillet 2025", "2025,2025-07", 0.90)])
    assert rag.search("salaire de juillet 2025", top_k=3, max_distance=0.34) == []


def test_l_ordre_semantique_est_conserve_dans_les_retenus():
    """La date décide QUI est éligible, le sémantique décide de l'ordre."""
    rag = _rag([
        ("extrait B", "2025,2025-07", 0.20),
        ("hors periode", "2026,2026-02", 0.22),
        ("extrait A", "2025,2025-07", 0.25),
    ])
    assert rag.search("juillet 2025", top_k=3) == ["extrait B", "extrait A"]


# ── Le RAG bredouille doit le DIRE ────────────────────────────────────

def test_une_recherche_infructueuse_est_annoncee_au_modele(monkeypatch):
    """
    ⚠️ Observé en conditions réelles, et c'est le pire échec de la série :
    sur « mon salaire de juillet 2024 », dont Cyril n'a aucun bulletin,
    rien n'était injecté — et le modèle a FABRIQUÉ un nom de fichier
    (« bulletin-de-paie-du-010724-au-310724.pdf ») et un montant
    (1650,89 €), en imitant le format des deux réponses correctes qui
    précédaient. Une réponse inventée est indiscernable d'une vraie.

    Le silence laisse le modèle combler le vide.
    """
    from core import lucas_core
    from core.lucas_core import LucasCore

    class _Memoire(MemoryDouble):
        def __init__(self):
            super().__init__()

        def load_history(self):
            return [("user", "mon salaire de juillet 2024")]

        def load_history_with_metadata(self):
            return [
                {"role": r, "message": m, "confidence": 1.0, "importance": 0.5, "expiration": None}
                for r, m in self.load_history()
            ]

        def load_recent_events(self, limit=5):
            return []

        def load_recent_events_with_metadata(self, limit=5):
            return []

        def save_event(self, *a, **k):
            pass

    class _RagVide:
        def get_context(self, query, top_k=3):
            return ""

    monkeypatch.setattr(lucas_core, "get_snapshot", dict)
    monkeypatch.setattr(
        lucas_core, "format_for_prompt", lambda s, include_window=True: "[système]"
    )
    monkeypatch.setattr(lucas_core, "should_use_rag", lambda text, context="": True)
    monkeypatch.setattr(lucas_core, "should_use_vision", lambda text, context="": False)
    monkeypatch.setattr(lucas_core, "RAGManager", _RagVide)

    core = LucasCore.__new__(LucasCore)
    core.memory = _Memoire()  # type: ignore[assignment]  # double assume, voir test_memory_double.py
    messages = core._build_messages("mon salaire de juillet 2024", "local")

    bloc = messages[-2]["content"]
    assert "AUCUN document ne correspond" in bloc
    # ⚠️ Un refus GÉNÉRIQUE ne suffisait pas : le modèle inventait quand
    # même. Nommer la période manquante lui donne quelque chose à dire,
    # là où « aucun document » le laissait chercher — et donc inventer.
    assert "2024-07" in bloc
    assert "INTERDIT" in bloc
    assert messages[-1]["content"] == "mon salaire de juillet 2024"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
