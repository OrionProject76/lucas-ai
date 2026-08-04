# test_weather_manager.py — météo actuelle via wttr.in
#
# Le point qui compte : ce module faisait planter son propre IMPORT (appel
# réseau réel dans du code de test sans garde `if __name__`), découvert en
# essayant d'importer chaque module du dépôt sans connexion internet. Ces
# tests vérifient le comportement, avec un faux `requests.get` — aucun appel
# réseau réel ici.
#
# ⚠️ Réponses factices ALIGNÉES sur le vrai service (vérifié en conditions
# réelles le 04/08/2026 en câblant ce module dans le chat) : `?format=3`
# rend en réalité UNE SEULE ligne (« Paris: ☀️  +23°C »), pas quatre comme
# une première version de ces tests le supposait — ce qui faisait passer
# TOUTE ville valide pour invalide (len(data) <= 1 toujours vrai). Remplacé
# par le format personnalisé `%l|%C|%t|%w|%h`, délimité par des barres :
# réponse réelle confirmée : "Paris|Clear |+23°C|↗13km/h|70%". Une ville
# invalide rend un code HTTP 500 (confirmé en réel :
# "location not found: upstream error...").

from __future__ import annotations

import pytest
import requests

from modules.weather_manager import WeatherManager


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code


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
    """Réponse réelle confirmée le 04/08/2026 : "Paris|Clear |+23°C|↗13km/h|70%"."""
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: _FakeResponse("Paris|Clear |+23°C|↗13km/h|70%")
    )

    resultat = manager.get_current("Paris")

    assert resultat is not None
    assert resultat["temperature"] == "+23°C"
    assert resultat["condition"] == "Clear"
    assert resultat["wind"] == "↗13km/h"
    assert resultat["humidity"] == "70%"


def test_une_ville_invalide_rend_un_statut_http_500(manager, monkeypatch):
    """
    Confirmé en conditions réelles : wttr.in ne rend pas une réponse
    normale mal formée, il rend un vrai code d'erreur HTTP.
    """
    monkeypatch.setattr(
        requests, "get",
        lambda *a, **k: _FakeResponse("location not found: upstream error", status_code=500),
    )

    assert manager.get_current("VilleInexistanteXYZ") is None


def test_une_reponse_incomplete_est_traitee_comme_invalide(manager, monkeypatch):
    """Filet de sécurité si wttr.in change de format sans passer par un statut d'erreur."""
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse("Paris|Clear"))

    assert manager.get_current("Paris") is None


def test_une_erreur_reseau_rend_none_sans_lever(manager, monkeypatch):
    def _leve_erreur_reseau(*args, **kwargs):
        raise requests.exceptions.ConnectionError("pas de réseau")

    monkeypatch.setattr(requests, "get", _leve_erreur_reseau)

    assert manager.get_current("Paris") is None


def test_format_for_display_sur_echec(manager):
    assert "invalide" in manager.format_for_display(None) or "pas de connexion" in manager.format_for_display(None)


def test_format_for_display_sur_succes(manager):
    """Température et humidité embarquent déjà leur unité — pas de doublon (°C°C, %%)."""
    data = {"temperature": "+18°C", "condition": "Clear", "wind": "↗10km/h", "humidity": "50%"}
    sortie = manager.format_for_display(data)

    assert "+18°C" in sortie
    assert "°C°C" not in sortie
    assert "Clear" in sortie
    assert "50%" in sortie
    assert "50%%" not in sortie


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
