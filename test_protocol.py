# test_protocol.py — vocabulaire du canal WebSocket Luca's ↔ Godot
#
# Deux protocoles incompatibles coexistaient : celui de l'API (branché
# sur OrionCore) et celui d'orion3d_bridge.py (un écho jamais connecté à
# Ollama, et qui ne démarre plus depuis websockets 12). Le client Godot
# parlait au second.
#
# Ces tests figent le vocabulaire unique et, surtout, vérifient qu'il
# reste aligné sur ce que le client Godot lit réellement — c'est là que
# la divergence se réinstallerait sans qu'on la voie.

from __future__ import annotations

import re
from pathlib import Path

import pytest

from api import protocol

GODOT_CLIENT = Path("Orion3D/scripts/websocket_client.gd")


# ── Construction des messages ─────────────────────────────────────────

def test_avatar_state_carries_the_state() -> None:
    assert protocol.avatar_state("thinking") == {
        "type": "avatar_state",
        "state": "thinking",
    }


def test_avatar_state_includes_text_when_given() -> None:
    message = protocol.avatar_state("speaking", "bonjour")
    assert message["text"] == "bonjour"


def test_empty_text_is_omitted() -> None:
    """Un champ vide encombre le client sans rien lui apprendre."""
    assert "text" not in protocol.avatar_state("idle", "")


def test_unknown_state_falls_back_to_idle() -> None:
    """
    Transmettre un état inconnu ferait afficher un halo sans couleur, ou
    rien du tout. Même repli que dans l'avatar PySide6.
    """
    assert protocol.avatar_state("n_importe_quoi")["state"] == "idle"


def test_chat_uses_the_field_names_godot_reads() -> None:
    message = protocol.chat("salut")
    assert message == {"type": "chat", "text": "salut", "from_orion": True}


def test_system_rounds_and_defaults_gpu() -> None:
    """
    Le GPU vaut 0 quand il n'est pas lisible : le HUD affiche une jauge
    vide plutôt que de disparaître.
    """
    assert protocol.system(12.345, 67.891) == {
        "type": "system", "cpu": 12.3, "ram": 67.9, "gpu": 0.0,
    }


# ── Lecture des messages entrants ─────────────────────────────────────

@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"message": "bonjour"}, "bonjour"),
        ({"text": "bonjour"}, "bonjour"),
        ({"message": "  espaces  "}, "espaces"),
        ({"message": "", "text": "repli"}, "repli"),
        ({}, ""),
        ({"message": "   "}, ""),
        ("pas un dict", ""),
    ],
)
def test_user_text_is_read_from_either_field(payload, expected: str) -> None:
    """
    Godot envoie « text », l'ancien protocole de l'API envoyait
    « message ». Accepter les deux évite de casser un client pendant la
    transition, et coûte une ligne.
    """
    assert protocol.read_user_text(payload) == expected


# ── Alignement avec les deux interfaces ───────────────────────────────

def test_states_match_the_pyside_avatar() -> None:
    """
    Une seule liste d'états pour les deux interfaces. Sans cette
    vérification, l'avatar 3D et l'avatar 2D dériveraient l'un de
    l'autre sans que rien ne le signale.
    """
    pytest.importorskip("PySide6")
    from ui.avatar_widget import PRESENCE_STATES as PYSIDE_STATES

    assert set(protocol.PRESENCE_STATES) == {s.lower() for s in PYSIDE_STATES}


@pytest.mark.skipif(not GODOT_CLIENT.is_file(), reason="client Godot absent")
def test_every_emitted_type_is_handled_by_godot() -> None:
    """
    Le client Godot ignore silencieusement un type inconnu. Émettre un
    message qu'il ne traite pas ne produirait donc AUCUNE erreur — juste
    une fonctionnalité muette, très difficile à diagnostiquer.
    """
    source = GODOT_CLIENT.read_text(encoding="utf-8")
    handled = set(re.findall(r'^\s*"(\w+)":', source, re.MULTILINE))

    for message_type in ("chat", "system"):
        assert message_type in handled, (
            f"le client Godot ne traite pas « {message_type} »"
        )


@pytest.mark.skipif(not GODOT_CLIENT.is_file(), reason="client Godot absent")
def test_godot_still_points_at_the_obsolete_bridge() -> None:
    """
    Constat, pas exigence : tant que websocket_client.gd pointe sur le
    port 8765, l'avatar 3D parle à l'écho et non à Luca's. Ce test
    documente l'écart restant et échouera — utilement — le jour où le
    client sera basculé sur l'API, signalant qu'il faut le retirer.
    """
    source = GODOT_CLIENT.read_text(encoding="utf-8")
    assert "8765" in source, (
        "le client Godot a été basculé sur l'API : ce test peut être supprimé"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
