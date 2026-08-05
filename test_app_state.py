# test_app_state.py — l'état persistant, testé contre le VRAI MemoryManager
#
# ⚠️ Pourquoi ce fichier existe (05/08/2026)
# ------------------------------------------
# `set_state`, `get_state` et `minutes_since_last_exchange` ont été écrits
# la nuit du 05/08 pour rendre le mode AURA « Deep Focus » réellement
# collant. Ils étaient exercés par les DOUBLES de test (`MemoryDouble`,
# `_FakeMemory`) — c'est-à-dire par des dictionnaires Python, jamais par
# SQLite. Couverture réelle constatée : 0 % sur ces trois méthodes.
#
# C'est exactement le motif traqué depuis deux jours : des tests verts sur
# un code dont le comportement réel n'a jamais été observé. Et il porte
# ici sur la seule chose que ces méthodes existent pour faire — SURVIVRE
# à la destruction de l'objet, ce qu'un dictionnaire simule parfaitement
# sans rien prouver.
#
# Chaque test travaille sur une base temporaire : jamais
# memory/lucas_memory.db. Cette précaution n'est pas décorative — une
# campagne de mesure a détruit ~56 messages réels de Cyril le 05/08 en
# croyant écrire sur une copie (ROADMAP.md §5.32).

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from core.aura_modes import AuraMode, AuraModeEngine
from memory.memory_manager import MemoryManager


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_memory.db"


@pytest.fixture
def memory(db_path):
    m = MemoryManager(db_path=db_path)
    yield m
    m.close()


# ── État persistant clé/valeur ────────────────────────────────────────


def test_a_written_state_can_be_read_back(memory) -> None:
    memory.set_state("mode", "focus")
    assert memory.get_state("mode") == "focus"


def test_an_absent_key_returns_the_default(memory) -> None:
    assert memory.get_state("jamais_ecrit") is None
    assert memory.get_state("jamais_ecrit", "repli") == "repli"


def test_writing_twice_replaces_instead_of_duplicating(memory) -> None:
    """
    La table a `key` en clé primaire : un second INSERT lèverait sans la
    clause ON CONFLICT. Un mode qu'on active puis désactive puis réactive
    est le cas NORMAL, pas un cas limite.
    """
    memory.set_state("mode", "on")
    memory.set_state("mode", "off")
    memory.set_state("mode", "on")
    assert memory.get_state("mode") == "on"
    conn = sqlite3.connect(memory.db_path)
    assert conn.execute("SELECT COUNT(*) FROM app_state").fetchone()[0] == 1
    conn.close()


def test_state_survives_the_object_being_destroyed(db_path) -> None:
    """
    LA propriété qui justifie l'existence de cette table. `LucasCore` est
    recréé à CHAQUE requête (contrainte SQLite/threads, api/server.py) :
    un état gardé en mémoire vive meurt entre deux messages de Cyril.

    Un double de test à base de dictionnaire passe ce scénario sans rien
    prouver — d'où ce test contre la vraie base.
    """
    premier = MemoryManager(db_path=db_path)
    premier.set_state("aura_deep_focus", "1")
    premier.close()

    second = MemoryManager(db_path=db_path)
    assert second.get_state("aura_deep_focus") == "1"
    second.close()


def test_db_path_is_exposed_so_a_caller_can_verify_it(db_path) -> None:
    """
    Ajouté après l'incident du 05/08 : une campagne de mesure croyait
    écrire sur une copie et écrivait dans la base de Cyril. Pouvoir
    VÉRIFIER la cible, au lieu de la supposer, est la parade.
    """
    m = MemoryManager(db_path=db_path)
    assert m.db_path == db_path
    m.close()


# ── Deep Focus de bout en bout, avec la vraie persistance ─────────────


def test_deep_focus_survives_a_new_engine_on_the_real_database(db_path) -> None:
    """
    Le scénario réel : Cyril demande le mode focus, puis envoie un autre
    message — donc un nouveau LucasCore, donc un nouveau moteur AURA.
    """
    def moteur():
        m = MemoryManager(db_path=db_path)
        return m, AuraModeEngine(
            store=(
                lambda: m.get_state("aura_deep_focus"),
                lambda v: m.set_state("aura_deep_focus", v),
            )
        )

    m1, e1 = moteur()
    e1.handle_command("active le mode focus")
    m1.close()

    m2, e2 = moteur()
    assert e2.detect("") is AuraMode.DEEP_FOCUS
    e2.handle_command("desactive le mode focus")   # sans accent, cas réel
    m2.close()

    m3, e3 = moteur()
    assert e3.detect("") is AuraMode.NONE
    m3.close()


# ── minutes_since_last_exchange ───────────────────────────────────────


def test_no_previous_exchange_returns_none(memory) -> None:
    """
    None veut dire « je ne sais pas », pas « à l'instant » : les deux
    mènent à un ton opposé, l'appelant doit pouvoir les distinguer.
    """
    assert memory.minutes_since_last_exchange() is None
    memory.save_message("user", "première question")
    assert memory.minutes_since_last_exchange() is None


def test_it_measures_from_the_second_to_last_message(memory) -> None:
    """
    AVANT-dernier, pas dernier : au moment de l'appel, la question
    courante vient d'être enregistrée par ask(). Mesurer depuis le dernier
    rendrait toujours ~0 — un signal de présence qui ne dit rien.
    """
    memory.save_message("user", "ancien")
    memory.save_message("assistant", "réponse")
    memory.save_message("user", "question courante")
    ecart = memory.minutes_since_last_exchange()
    assert ecart is not None
    assert ecart < 1


def test_an_old_exchange_is_measured_in_the_past(memory) -> None:
    memory.save_message("user", "il y a longtemps")
    memory.save_message("user", "question courante")
    vieux = (datetime.now(UTC) - timedelta(hours=20)).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(memory.db_path)
    conn.execute(
        "UPDATE conversations SET created_at = ? WHERE id = "
        "(SELECT id FROM conversations ORDER BY id DESC LIMIT 1 OFFSET 1)",
        (vieux,),
    )
    conn.commit()
    conn.close()

    ecart = memory.minutes_since_last_exchange()
    assert ecart is not None
    assert 1150 < ecart < 1250   # ~1200 minutes = 20 h


def test_an_unparsable_timestamp_returns_none_instead_of_raising(memory) -> None:
    """
    Un horodatage illisible ne doit jamais empêcher de répondre : c'est un
    signal de confort, pas une donnée critique.
    """
    memory.save_message("user", "a")
    memory.save_message("user", "b")
    conn = sqlite3.connect(memory.db_path)
    conn.execute(
        "UPDATE conversations SET created_at = 'pas une date' WHERE id = "
        "(SELECT id FROM conversations ORDER BY id DESC LIMIT 1 OFFSET 1)"
    )
    conn.commit()
    conn.close()

    assert memory.minutes_since_last_exchange() is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
