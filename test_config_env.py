# test_config_env.py — ce que l'environnement a le droit de changer
#
# ⚠️ La panne réelle qui a fait naître ce fichier (12/08/2026, §5.94)
# --------------------------------------------------------------------
# `config.py` lisait la variable d'environnement `OLLAMA_HOST` pour en
# faire l'URL d'appel : `OLLAMA_URL = f"{OLLAMA_HOST}/api/chat"`.
#
# Sauf que ce nom ne nous appartient pas. `OLLAMA_HOST` est la variable
# STANDARD d'Ollama, et elle répond à une question opposée à la nôtre :
# sur quelle interface le SERVEUR ollama doit ÉCOUTER. Cyril l'avait
# posée à « 0.0.0.0 » — la valeur recommandée pour rendre Ollama
# joignable depuis le téléphone, donc un réglage parfaitement légitime.
#
# Effet mesuré sur sa machine : `0.0.0.0/api/chat`, sans schéma ni port.
# TOUTE question locale répondait « [Erreur] Problème réseau avec
# Ollama », et les embeddings RAG tombaient de la même façon. Une panne
# totale du cerveau local, causée par un réglage correct posé ailleurs.
#
# Ces tests figent la leçon : emprunter le nom d'une variable d'un autre
# programme, c'est hériter de ses valeurs — y compris celles qui n'ont
# aucun sens pour nous.

from __future__ import annotations

import importlib

import pytest


def _reload_config(monkeypatch, **env):
    """Recharge config.py avec un environnement contrôlé."""
    import config

    for name in ("OLLAMA_HOST", "LUCAS_OLLAMA_HOST"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return importlib.reload(config)


@pytest.fixture(autouse=True)
def _restore_config():
    """
    Recharge la config d'origine après chaque test.

    Sans ça, un `importlib.reload` laisserait le module modifié pour
    TOUTE la suite — les tests suivants hériteraient d'une URL de test.
    """
    yield
    import config

    importlib.reload(config)


def test_the_ollama_server_variable_is_not_borrowed(monkeypatch) -> None:
    """
    LE test de la panne : « OLLAMA_HOST=0.0.0.0 » est un réglage valide
    du serveur Ollama, il ne doit plus pouvoir casser l'URL cliente.
    """
    config = _reload_config(monkeypatch, OLLAMA_HOST="0.0.0.0")

    assert config.OLLAMA_URL == "http://127.0.0.1:11434/api/chat"
    assert "0.0.0.0" not in config.OLLAMA_URL


def test_the_dedicated_variable_is_still_honoured(monkeypatch) -> None:
    """
    La surcharge reste possible — c'est ce qui permet de pointer la
    suite vers un port mort pour mesurer sa dépendance réelle à Ollama
    (raison d'être de conftest.py, §5.42). Seul le NOM a changé.
    """
    config = _reload_config(monkeypatch, LUCAS_OLLAMA_HOST="http://127.0.0.1:9999")

    assert config.OLLAMA_URL == "http://127.0.0.1:9999/api/chat"


def test_the_dedicated_variable_wins_over_the_ollama_one(monkeypatch) -> None:
    """
    Les deux posées en même temps : la nôtre décide. Sinon le correctif
    ne tiendrait pas sur la machine de Cyril, où `OLLAMA_HOST` est
    définie de façon persistante.
    """
    config = _reload_config(
        monkeypatch,
        OLLAMA_HOST="0.0.0.0",
        LUCAS_OLLAMA_HOST="http://127.0.0.1:11434",
    )

    assert config.OLLAMA_URL == "http://127.0.0.1:11434/api/chat"


def test_the_default_stays_the_measured_one(monkeypatch) -> None:
    """
    127.0.0.1 et jamais « localhost » : Windows résout localhost en IPv6
    d'abord, Ollama n'écoute qu'en IPv4, et chaque appel payait ~2 s de
    timeout de résolution (config.py, mesure du 05/08/2026).
    """
    config = _reload_config(monkeypatch)

    assert config.OLLAMA_URL == "http://127.0.0.1:11434/api/chat"
    assert "localhost" not in config.OLLAMA_URL


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
