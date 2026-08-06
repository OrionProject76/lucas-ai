# test_silent_failures.py — aucune capacité ne doit échouer en silence
#
# ⚠️ La famille de bugs que ce fichier verrouille
# ------------------------------------------------
# Elle est apparue trois fois en deux jours, sous trois visages :
#
#   §5.31  une action non exécutée n'injectait AUCUN contexte, et le modèle
#          a répondu « Le Bloc-notes est lancé » alors que rien n'avait été
#          tenté ;
#   §5.32  une panne d'embedding faisait remonter l'exception jusqu'à
#          l'API — Cyril n'obtenait aucune réponse du tout ;
#   §5.39  une recherche web échouée, vide ou REFUSÉE pour donnée
#          personnelle était injectée sous l'étiquette « RECHERCHE WEB
#          RÉELLE » suivie de « appuie-toi uniquement sur ces résultats
#          réels ».
#
# La règle qui s'en dégage, et que ces tests protègent :
#   toute capacité qui peut ne pas s'exécuter doit injecter un contexte
#   EXPLICITE quand elle ne s'exécute pas — le silence n'est jamais neutre,
#   et une étiquette fausse est pire qu'un silence.

from __future__ import annotations

import pytest

from core import lucas_core
from core.lucas_core import LucasCore
from test_memory_double import MemoryDouble


class _Memoire(MemoryDouble):
    pass


@pytest.fixture
def core(monkeypatch):
    monkeypatch.setattr(lucas_core, "get_snapshot", dict)
    monkeypatch.setattr(
        lucas_core, "format_for_prompt",
        lambda snapshot, include_window=True: "[système]",
    )
    instance = LucasCore.__new__(LucasCore)
    instance.memory = _Memoire()  # type: ignore[assignment]  # double assume, voir test_memory_double.py
    return instance


def _bloc_systeme(messages) -> str:
    return "\n".join(m["content"] for m in messages if m["role"] == "system")


# ── Recherche web : les 4 issues doivent être distinguables ───────────


def _faux_websearch(monkeypatch, resultats):
    class _FauxDDGS:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def text(self, query, max_results=5):
            return resultats

    monkeypatch.setattr("modules.web_search.DDGS", _FauxDDGS)


def test_a_successful_search_is_labelled_real(core, monkeypatch) -> None:
    _faux_websearch(monkeypatch, [{"title": "Un titre", "href": "http://x", "body": "un corps"}])
    bloc = _bloc_systeme(core._build_messages("cherche sur internet les news", "local"))
    assert "RECHERCHE WEB RÉELLE" in bloc


def test_an_empty_search_says_so_instead_of_claiming_results(core, monkeypatch) -> None:
    _faux_websearch(monkeypatch, [])
    bloc = _bloc_systeme(core._build_messages("cherche sur internet les news", "local"))
    assert "AUCUN RÉSULTAT" in bloc
    assert "RECHERCHE WEB RÉELLE" not in bloc


def test_a_failed_search_is_never_presented_as_real_results(core, monkeypatch) -> None:
    """
    Une panne réseau était injectée comme « RECHERCHE WEB RÉELLE » suivie
    de « appuie-toi uniquement sur ces résultats réels ». Le modèle était
    donc explicitement invité à s'appuyer sur un message d'erreur.
    """
    class _DDGSCasse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def text(self, query, max_results=5):
            raise ConnectionError("réseau injoignable")

    monkeypatch.setattr("modules.web_search.DDGS", _DDGSCasse)
    bloc = _bloc_systeme(core._build_messages("cherche sur internet les news", "local"))
    assert "A ÉCHOUÉ" in bloc
    assert "RECHERCHE WEB RÉELLE" not in bloc


def test_a_privacy_refusal_is_never_presented_as_real_results(core, monkeypatch) -> None:
    """
    Le cas le plus grave des quatre : Luca REFUSE de chercher parce que la
    question contient une donnée identifiante — et ce refus arrivait au
    modèle étiqueté « résultats réels », donc utilisable comme tel.
    """
    def _ne_doit_pas_etre_appele(*a, **k):
        raise AssertionError("aucun appel réseau ne doit partir sur un refus")

    monkeypatch.setattr("modules.web_search.DDGS", _ne_doit_pas_etre_appele)
    bloc = _bloc_systeme(
        core._build_messages(
            "cherche sur internet mon IBAN FR76 3000 4000 0512 3456 7890 123", "local"
        )
    )
    if "REFUSÉE" in bloc:
        assert "RECHERCHE WEB RÉELLE" not in bloc
        assert "protection volontaire" in bloc


# ── Le RAG ne doit pas faire tomber la requête entière ────────────────


def test_a_rag_failure_degrades_instead_of_crashing(core, monkeypatch) -> None:
    """
    Régression du 05/08/2026 : une réponse d'embedding sans champ
    « embedding » remontait jusqu'à l'API en HTTP 500. Cyril n'obtenait
    pas une réponse dégradée — il n'obtenait RIEN.
    """
    class _RagCasse:
        def get_context(self, query):
            raise RuntimeError("échec de l'embedding")

    monkeypatch.setattr(lucas_core, "RAGManager", _RagCasse)
    monkeypatch.setattr(lucas_core, "should_use_rag", lambda *a, **k: True)

    bloc = _bloc_systeme(core._build_messages("que dit le document sur mon CV", "local"))
    assert "ÉCHOUÉ" in bloc
    assert "AUCUN document" in bloc


def test_the_rag_failure_block_forbids_answering_from_memory(core, monkeypatch) -> None:
    """
    Le repli doit interdire explicitement de répondre de mémoire générale
    en laissant croire que ça vient des documents — sinon on remplace une
    panne visible par une invention crédible.
    """
    class _RagCasse:
        def get_context(self, query):
            raise RuntimeError("boom")

    monkeypatch.setattr(lucas_core, "RAGManager", _RagCasse)
    monkeypatch.setattr(lucas_core, "should_use_rag", lambda *a, **k: True)

    bloc = _bloc_systeme(core._build_messages("que dit le document sur mon CV", "local"))
    assert "INTERDIT" in bloc


# ── Une demande d'action non exécutable ne doit pas être muette ───────


def test_an_unknown_app_request_produces_an_explicit_block(core) -> None:
    bloc = _bloc_systeme(core._build_messages("ouvre spotify", "local"))
    assert "AUCUNE ACTION N'A ÉTÉ EFFECTUÉE" in bloc


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
