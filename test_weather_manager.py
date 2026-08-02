# test_weather_manager.py — météo actuelle via wttr.in
#
# Le point qui compte : ce module faisait planter son propre IMPORT (appel
# réseau réel dans du code de test sans garde `if __name__`), découvert en
# essayant d'importer chaque module du dépôt sans connexion internet. Ces
# tests vérifient le comportement, avec un faux `requests.get` — aucun appel
# réseau réel ici.

from __future__ import annotations

import pytest
import requests

from modules.weather_manager import WeatherManager


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


@pytest.fixture
def manager():
    return WeatherManager()


def test_importer_le_module_ne_declenche_aucun_appel_reseau(monkeypatch):
    """
    LE bug trouvé par l'audit : un bloc en bas de fichier, sans garde,
    appelait requests.get() dès l'import — ce qui plantait sur une machine
    sans réseau, au lieu de se contenter de définir la classe.
    """

    def _echoue_si_appele(*args, **kwargs):
        raise AssertionError("requests.get() appelé à l'import")

    monkeypatch.setattr(requests, "get", _echoue_si_appele)

    import importlib

    import modules.weather_manager as wm

    importlib.reload(wm)  # ré-exécute le module ; ne doit rien appeler


def test_une_reponse_valide_est_analysee(manager, monkeypatch):
    """
    ⚠️ Ce test vérifie l'ANALYSE des 4 lignes attendues par le code
    (température, condition, vent, humidité) — pas que ce format
    corresponde réellement à ce que wttr.in renvoie. L'URL interrogée
    (`?format=3`) rend en pratique une seule ligne compacte : le format
    à 4 lignes ici imite l'hypothèse du code, non une réponse réelle
    observée. Une vérification contre le vrai service reste à faire.
    """
    texte = "Paris: soleil +18°C\nsoleil degage\nvent 12 kmh\nhumidite 64 pourcent"
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse(texte))

    resultat = manager.get_current("Paris")

    assert resultat is not None
    assert resultat["temperature"] == "+18°C"


def test_une_reponse_trop_courte_est_une_ville_invalide(manager, monkeypatch):
    """
    Avant la correction, cette branche levait ValueError("Ville invalide")
    — non rattrapée par le except sur RequestException, elle remontait donc
    jusqu'à l'appelant au lieu de rendre None comme le reste du contrat.
    """
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse("une seule ligne"))

    assert manager.get_current("VilleInexistanteXYZ") is None


def test_une_erreur_reseau_rend_none_sans_lever(manager, monkeypatch):
    def _leve_erreur_reseau(*args, **kwargs):
        raise requests.exceptions.ConnectionError("pas de réseau")

    monkeypatch.setattr(requests, "get", _leve_erreur_reseau)

    assert manager.get_current("Paris") is None


def test_format_for_display_sur_echec(manager):
    assert "invalide" in manager.format_for_display(None) or "pas de connexion" in manager.format_for_display(None)


def test_format_for_display_sur_succes(manager):
    data = {"temperature": "18", "condition": "Ensoleillé", "wind": "10", "humidity": "50"}
    sortie = manager.format_for_display(data)

    assert "18" in sortie
    assert "Ensoleillé" in sortie


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
