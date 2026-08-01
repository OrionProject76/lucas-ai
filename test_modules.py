# test_modules.py — vision et recherche web
#
# Aucun appel réseau, aucun VLM, aucune capture d'écran réelle : Ollama,
# ImageGrab et DuckDuckGo sont remplacés par des doubles.

from __future__ import annotations

import pytest

from modules import vision_manager as vm_module
from modules import web_search as ws_module
from modules.vision_manager import VisionManager
from modules.web_search import WebSearch

# ── VisionManager ─────────────────────────────────────────────────────

class _FakeImage:
    def __init__(self) -> None:
        self.saved_to: str | None = None

    def save(self, path) -> None:
        self.saved_to = str(path)
        # ImageGrab produit un vrai fichier : on imite pour la suite du test.
        from pathlib import Path
        Path(path).write_bytes(b"\x89PNG fake")


def test_capture_creates_the_parent_directory(tmp_path, monkeypatch) -> None:
    """
    Un data/ absent faisait échouer la capture sur un FileNotFoundError
    peu parlant. Le répertoire doit être créé au besoin.
    """
    monkeypatch.setattr(vm_module.ImageGrab, "grab", lambda: _FakeImage())

    target = tmp_path / "sous" / "dossier" / "shot.png"
    result = VisionManager().capture_screen(str(target))

    assert target.exists()
    assert result == str(target)


def test_analyze_reports_missing_ollama(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(vm_module, "ollama", None)
    assert "non installé" in VisionManager().analyze_image(str(tmp_path / "x.png"))


def test_analyze_reports_unreadable_image(monkeypatch, tmp_path) -> None:
    """Un fichier absent ne doit pas remonter une OSError brute à l'UI."""
    monkeypatch.setattr(vm_module, "ollama", object())
    result = VisionManager().analyze_image(str(tmp_path / "absente.png"))
    assert "illisible" in result


def test_analyze_sends_the_image_to_the_local_model(monkeypatch, tmp_path) -> None:
    image = tmp_path / "shot.png"
    image.write_bytes(b"contenu binaire")
    captured: dict = {}

    class _FakeOllama:
        @staticmethod
        def chat(model, messages):
            captured["model"] = model
            captured["messages"] = messages
            return {"message": {"content": "un bureau avec du code"}}

    monkeypatch.setattr(vm_module, "ollama", _FakeOllama)
    result = VisionManager(model="llava").analyze_image(str(image))

    assert result == "un bureau avec du code"
    assert captured["model"] == "llava"
    assert captured["messages"][0]["images"], "l'image doit être jointe en base64"


def test_vlm_failure_returns_a_message_not_an_exception(monkeypatch, tmp_path) -> None:
    """Un VLM injoignable ne doit pas faire tomber l'UI ni le daemon."""
    image = tmp_path / "shot.png"
    image.write_bytes(b"x")

    class _Broken:
        @staticmethod
        def chat(model, messages):
            raise ConnectionError("Ollama injoignable")

    monkeypatch.setattr(vm_module, "ollama", _Broken)
    assert "Erreur analyse" in VisionManager().analyze_image(str(image))


def test_screenshot_never_leaves_the_machine() -> None:
    """
    Garde anti-régression : une capture d'écran peut contenir un relevé
    bancaire ou un mot de passe. L'analyse passe par Ollama en local,
    jamais par une API cloud (CLAUDE.md règle 3).
    """
    import inspect

    source = inspect.getsource(vm_module)
    for forbidden in ("openai", "requests.post", "https://", "ask_cloud"):
        assert forbidden not in source


# ── WebSearch ─────────────────────────────────────────────────────────

class _FakeDDGS:
    def __init__(self) -> None:
        self.results: list[dict] = []
        self.raises: Exception | None = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def text(self, query, max_results=5):
        if self.raises:
            raise self.raises
        return self.results[:max_results]


@pytest.fixture
def fake_ddgs(monkeypatch):
    fake = _FakeDDGS()
    monkeypatch.setattr(ws_module, "DDGS", lambda: fake)
    return fake


def test_search_returns_results(fake_ddgs) -> None:
    fake_ddgs.results = [{"title": "T", "href": "http://x", "body": "B"}]
    assert WebSearch().search("test") == fake_ddgs.results


def test_network_failure_degrades_without_raising(fake_ddgs) -> None:
    fake_ddgs.raises = ConnectionError("pas de réseau")
    results = WebSearch().search("test")
    assert results[0]["title"] == "Erreur"
    assert "Impossible de rechercher" in results[0]["body"]


def test_summary_handles_missing_fields(fake_ddgs) -> None:
    """Les résultats DDG n'ont pas toujours tous les champs."""
    fake_ddgs.results = [{}]
    summary = WebSearch().get_summary("test")
    assert "Sans titre" in summary
    assert "Pas de description" in summary


def test_summary_without_results(fake_ddgs) -> None:
    fake_ddgs.results = []
    assert "Aucun résultat" in WebSearch().get_summary("test")


def test_long_snippets_are_truncated(fake_ddgs) -> None:
    fake_ddgs.results = [{"title": "T", "href": "h", "body": "x" * 500}]
    summary = WebSearch().get_summary("test")
    assert "..." in summary
    assert "x" * 200 not in summary


def test_short_snippet_gets_no_ellipsis(fake_ddgs) -> None:
    fake_ddgs.results = [{"title": "T", "href": "h", "body": "court"}]
    assert "court..." not in WebSearch().get_summary("test")


# ── WebSearch : filtre des données identifiantes ──────────────────────

@pytest.mark.parametrize(
    "query",
    [
        "mon IBAN",
        "quel est mon solde",
        "mon numéro de carte",
        "FR76 3000 4000 0512 3456 7890 123",
        "4539 1488 0343 6467",
        "mon mot de passe wifi",
    ],
)
def test_identifying_queries_are_refused(query: str, fake_ddgs) -> None:
    """Ces requêtes désignent les données de Cyril, pas un sujet de recherche."""
    fake_ddgs.results = [{"title": "ne doit pas apparaître", "href": "", "body": ""}]
    results = WebSearch().search(query)
    assert results[0]["title"] == "Recherche annulée"


@pytest.mark.parametrize(
    "query",
    [
        "quel est le meilleur crédit immobilier",
        "comment changer de banque",
        "taux d'intérêt 2026",
        "budget moyen d'un ménage français",
        "risque sismique en France",
        "portfolio management définition",
    ],
)
def test_legitimate_searches_are_not_blocked(query: str, fake_ddgs) -> None:
    """
    Le filtre est volontairement plus étroit que KEYWORDS_SENSITIVE :
    « crédit », « banque », « budget », « risque » et « portfolio » ont
    un usage de recherche parfaitement légitime. Un filtre qui empêche
    l'usage normal finit désactivé, donc inutile.
    """
    fake_ddgs.results = [{"title": "résultat", "href": "", "body": ""}]
    assert WebSearch().search(query)[0]["title"] == "résultat"


def test_refused_query_makes_no_network_call(monkeypatch) -> None:
    """Le refus doit intervenir AVANT tout appel à DuckDuckGo."""
    def must_not_be_called():
        raise AssertionError("aucune requête ne doit partir")

    monkeypatch.setattr(ws_module, "DDGS", must_not_be_called)
    WebSearch().search("mon IBAN est FR76 3000 4000 0512 3456 7890 123")


def test_refusal_is_logged(fake_ddgs) -> None:
    events: list[tuple[str, str]] = []
    WebSearch(log_event=lambda t, d="": events.append((t, d))).search("mon solde")
    assert [t for t, _ in events] == ["websearch_refused"]


def test_logged_query_is_truncated(fake_ddgs) -> None:
    """Le journal ne doit pas devenir une copie de la donnée refusée."""
    events: list[tuple[str, str]] = []
    WebSearch(log_event=lambda t, d="": events.append((t, d))).search("mon solde " + "x" * 500)
    assert len(events[0][1]) <= 80


def test_a_year_is_not_mistaken_for_a_card_number(fake_ddgs) -> None:
    """Garde-fou sur le motif numérique : 2026 ne doit rien déclencher."""
    fake_ddgs.results = [{"title": "résultat", "href": "", "body": ""}]
    assert WebSearch().search("météo 2026")[0]["title"] == "résultat"


def test_max_results_is_honored(fake_ddgs) -> None:
    fake_ddgs.results = [{"title": str(i), "href": "", "body": ""} for i in range(10)]
    assert len(WebSearch().search("test", max_results=3)) == 3


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
