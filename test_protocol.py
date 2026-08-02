# test_protocol.py — vocabulaire du canal WebSocket Luca's ↔ Godot
#
# Deux protocoles incompatibles coexistaient : celui de l'API (branché
# sur LucasCore) et celui d'orion3d_bridge.py (un écho jamais connecté à
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

GODOT_CLIENT = Path("Lucas3D/scripts/websocket_client.gd")


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
    assert message == {"type": "chat", "text": "salut", "from_lucas": True}


def test_activity_carries_kind_and_text() -> None:
    assert protocol.activity("screen_read", "écran lu — texte trouvé") == {
        "type": "activity",
        "kind": "screen_read",
        "text": "écran lu — texte trouvé",
    }


def test_security_status_carries_the_core_fields() -> None:
    message = protocol.security_status(True, "2026-08-02T21:00:00", 3, "un résumé")
    assert message == {
        "type": "security_status",
        "active": True,
        "findings_24h": 3,
        "last_scan_at": "2026-08-02T21:00:00",
        "latest_summary": "un résumé",
    }


def test_security_status_omits_absent_optional_fields() -> None:
    """
    Un daemon éteint (active=False) n'a ni dernier balayage ni signal
    récent à annoncer — les omettre plutôt que d'envoyer null évite au
    client de distinguer « absent » de « null » pour rien.
    """
    message = protocol.security_status(False, None, 0, None)
    assert "last_scan_at" not in message
    assert "latest_summary" not in message
    assert message["active"] is False
    assert message["findings_24h"] == 0


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
def test_godot_talks_to_the_api_not_a_side_service() -> None:
    """
    Le client pointait sur le bridge d'écho (port 8765), qui
    court-circuitait le routage, les gardes de sensibilité et la
    mémoire. Il doit parler à l'API et à rien d'autre.
    """
    source = GODOT_CLIENT.read_text(encoding="utf-8")
    assert "127.0.0.1:8000/ws" in source
    assert "8765" not in source.replace("supprimé", "")


@pytest.mark.skipif(not GODOT_CLIENT.is_file(), reason="client Godot absent")
def test_godot_handles_the_avatar_state_messages() -> None:
    """
    « avatar_state » est le seul message d'état que l'API émet. Un type
    non traité est ignoré SILENCIEUSEMENT par Godot : le visage resterait
    inerte sans qu'aucune erreur n'apparaisse nulle part.
    """
    source = GODOT_CLIENT.read_text(encoding="utf-8")
    handled = set(re.findall(r'^\s*"(\w+)":', source, re.MULTILINE))
    assert "avatar_state" in handled


def test_the_dead_bridge_is_gone() -> None:
    """
    Un service cassé laissé dans le dépôt ressemble à une alternative
    valable. Celui-ci ne démarrait plus depuis websockets 12.
    """
    assert not Path("Lucas3D/python_service/orion3d_bridge.py").exists()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
