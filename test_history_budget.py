# test_history_budget.py — le prompt système ne doit pas se faire noyer
#
# Troisième visage du bug de dilution, après la vision et le RAG. Les deux
# premiers ne se déclenchaient que quand une source externe était injectée ;
# celui-ci frappe les questions ORDINAIRES, qui recevaient les 100 messages
# d'historique en entier.
#
# Mesuré sur la base réelle de Cyril, deux règles indépendantes du prompt
# système (une d'identité, une de sécurité), 9 tirages : les deux tombent
# de 9/9 sans historique à 1/9 et 2/9 sous 100 messages. Tableaux complets
# dans config.py (HISTORY_BUDGET_CHARS).

import pytest

from config import (
    HISTORY_BUDGET_CHARS,
    HISTORY_MESSAGE_MAX_CHARS,
    HISTORY_RECENT_MAX_CHARS,
    SYSTEM_PROMPT,
)
from core import lucas_core
from core.lucas_core import LucasCore, fit_history_to_budget


# ── fit_history_to_budget() ───────────────────────────────────────────

def test_the_budget_is_a_volume_not_a_message_count() -> None:
    """
    LE point du correctif. Ce qui dilue le prompt système est le VOLUME de
    texte, pas le nombre de tours : 30 messages courts pèsent moins que
    6 messages longs, et gardent cinq fois plus de contexte.
    """
    courts = [("user", "ok")] * 60
    longs = [("user", "x" * 500)] * 60

    assert len(fit_history_to_budget(courts)) > len(fit_history_to_budget(longs)), (
        "un plafond en nombre de messages garderait autant des deux — "
        "c'est précisément l'erreur que ce budget corrige"
    )


def test_the_budget_is_respected() -> None:
    history = [("user", "x" * 400)] * 50
    kept = fit_history_to_budget(history)
    volume = sum(len(content) for _role, content in kept)
    assert volume <= HISTORY_BUDGET_CHARS, f"{volume} caractères joints"


def test_old_messages_are_truncated_not_dropped() -> None:
    """
    Tronquer plutôt que jeter : le fil d'une conversation se retient dans
    les premières phrases. Jeter les messages entiers coûterait la
    continuité sans rien gagner sur la dilution.
    """
    history = [("assistant", "début du message. " + "bla " * 300)] * 10
    kept = fit_history_to_budget(history)

    ancien = kept[0][1]
    assert ancien.startswith("début du message."), "le début doit survivre"
    assert len(ancien) <= HISTORY_MESSAGE_MAX_CHARS, "…mais pas la suite"


def test_no_truncation_marker_is_added() -> None:
    """
    La première version terminait les messages coupés par « […] ». Trouvé
    en test réel via l'API : le modèle RECOPIE le marqueur et coupe sa
    propre réponse en plein mot (« 2. **Interfa […] »). Mesuré 1/9 avec,
    0/9 sans.

    Tout motif régulier ajouté à l'historique est un exemple à imiter —
    c'est le bug qu'on corrige ici, appliqué à la forme au lieu du fond.
    """
    kept = fit_history_to_budget([("assistant", "mot " * 300)] * 5)
    assert not any("[…]" in content for _role, content in kept)
    assert not any("..." in content for _role, content in kept)


def test_truncation_falls_on_a_word_boundary() -> None:
    """Une coupe en plein mot est elle aussi un motif imitable."""
    kept = fit_history_to_budget([("assistant", "auberge " * 200)] * 5)
    assert kept[0][1].endswith("auberge"), f"coupé sur : {kept[0][1][-20:]!r}"


def test_the_last_exchange_keeps_more_room() -> None:
    """
    « Et pour 2024 ? » n'a de sens que par rapport à la réponse juste
    avant. Vérifié : cette exception ne coûte rien à la mesure (7/9 et
    9/9, identiques à la troncature uniforme).
    """
    long_texte = "mot " * 300
    history = [("user", long_texte), ("assistant", long_texte)] * 5
    kept = fit_history_to_budget(history)

    assert len(kept[-1][1]) > HISTORY_MESSAGE_MAX_CHARS
    assert len(kept[-1][1]) <= HISTORY_RECENT_MAX_CHARS + 10
    assert len(kept[0][1]) <= HISTORY_MESSAGE_MAX_CHARS + 10


def test_at_least_one_message_survives() -> None:
    """
    Un seul message plus gros que le budget entier ne doit pas laisser
    Luca's sans aucun contexte : perdre le fil au milieu d'une phrase se
    voit davantage que la dilution qu'on corrige.
    """
    assert fit_history_to_budget([("user", "x" * (HISTORY_BUDGET_CHARS * 3))])


def test_an_empty_history_stays_empty() -> None:
    assert fit_history_to_budget([]) == []


# ── Intégration dans _build_messages() ────────────────────────────────

class _FakeMemory:
    def __init__(self, history: list[tuple[str, str]]) -> None:
        self._history = history

    def load_history(self) -> list[tuple[str, str]]:
        return self._history

    def load_history_with_metadata(self) -> list[dict]:
        return [
            {"role": r, "message": m, "confidence": 1.0, "importance": 0.5, "expiration": None}
            for r, m in self._history
        ]

    def load_recent_events(self, limit: int = 5) -> list[tuple[str, str, str]]:
        return []

    def load_recent_events_with_metadata(self, limit: int = 5) -> list[dict]:
        return []


def _core(monkeypatch, history: list[tuple[str, str]]) -> LucasCore:
    monkeypatch.setattr(lucas_core, "get_snapshot", dict)
    monkeypatch.setattr(
        lucas_core, "format_for_prompt",
        lambda snapshot, include_window=True: "[système]",
    )
    monkeypatch.setattr(lucas_core, "should_use_vision", lambda text, context="": False)
    monkeypatch.setattr(lucas_core, "should_use_rag", lambda text, context="": False)
    instance = LucasCore.__new__(LucasCore)
    instance.memory = _FakeMemory(history)
    return instance


@pytest.fixture
def core_long(monkeypatch) -> LucasCore:
    """Une conversation réaliste : 50 échanges de réponses verbeuses."""
    history: list[tuple[str, str]] = []
    for i in range(50):
        history.append(("user", f"question {i} " + "bla " * 40))
        history.append(("assistant", f"réponse {i} " + "bla " * 120))
    history.append(("user", "que voudrais-tu améliorer ?"))
    return _core(monkeypatch, history)


def test_an_ordinary_question_no_longer_receives_the_whole_history(core_long) -> None:
    """
    Le bug signalé par Cyril. Aucune source externe n'est déclenchée ici :
    avant le correctif, les 100 messages partaient tels quels.
    """
    messages = core_long._build_messages("que voudrais-tu améliorer ?", "local")
    conversation = [m for m in messages if m["role"] != "system"]

    volume = sum(len(m["content"]) for m in conversation)
    assert volume <= HISTORY_BUDGET_CHARS + len("que voudrais-tu améliorer ?")


def test_the_system_prompt_is_repeated_just_before_the_question(core_long) -> None:
    """
    Le ré-ancrage. Il ne remplace pas le budget — seul, il ne corrige rien
    sur une règle d'identité (1/9 → 1/9) — mais il rattrape les règles
    factuelles, dont celles de sécurité (2/9 → 7/9).
    """
    messages = core_long._build_messages("que voudrais-tu améliorer ?", "local")

    rappels = [i for i, m in enumerate(messages) if m["content"] == SYSTEM_PROMPT]
    assert len(rappels) == 2, "le prompt système ouvre le prompt ET le referme"
    assert rappels[0] == 0
    assert rappels[1] == len(messages) - 2, (
        "le rappel doit être immédiatement avant la question ; plus haut, "
        "il se ferait noyer par l'historique comme le premier"
    )


def test_the_question_stays_last(core_long) -> None:
    messages = core_long._build_messages("que voudrais-tu améliorer ?", "local")
    assert messages[-1]["content"] == "que voudrais-tu améliorer ?"
    assert messages[-1]["role"] == "user"


def test_no_reanchor_without_history(monkeypatch) -> None:
    """
    Sans historique, rien ne dilue : répéter le prompt système n'aurait
    aucun effet et doublerait le coût du contexte pour rien.
    """
    core = _core(monkeypatch, [("user", "bonjour")])
    messages = core._build_messages("bonjour", "local")
    assert sum(m["content"] == SYSTEM_PROMPT for m in messages) == 1


def test_the_budget_also_applies_to_the_cloud(monkeypatch) -> None:
    """
    Point de sécurité, pas seulement de qualité : le budget ne peut que
    RÉDUIRE ce qui sort de la machine. CLOUD_HISTORY_MESSAGES reste le
    plafond en nombre de messages, le budget s'y ajoute.
    """
    history = [("user", "x" * 3000), ("assistant", "y" * 3000)] * 5
    history.append(("user", "compare ces options"))
    core = _core(monkeypatch, history)

    messages = core._build_messages("compare ces options", "cloud")
    conversation = [m for m in messages if m["role"] != "system"]
    volume = sum(len(m["content"]) for m in conversation)

    assert volume <= HISTORY_BUDGET_CHARS + len("compare ces options"), (
        f"{volume} caractères envoyés hors de la machine"
    )


# ── Oublier un échange raté ───────────────────────────────────────────
#
# Le budget empêche une mauvaise réponse d'en contaminer cent. Il ne peut
# pas effacer celle qui vient d'être donnée : face à la même question
# répondue juste au-dessus, le modèle imite sa propre réponse. Mesuré sur
# la base réelle de Cyril : 3/9 avec l'échange raté, 8/9 en retirant
# quatre messages. D'où `just forget-last`.

@pytest.fixture
def memory(tmp_path):
    from memory.memory_manager import MemoryManager

    instance = MemoryManager(db_path=tmp_path / "test.db")
    yield instance
    instance.close()


def test_forget_last_exchange_removes_the_question_and_its_answer(memory) -> None:
    memory.save_message("user", "première question")
    memory.save_message("assistant", "première réponse")
    memory.save_message("user", "que souhaites-tu vraiment ?")
    memory.save_message("assistant", "réponse générique ratée")

    assert memory.forget_last_exchange() == 2
    assert memory.load_history() == [
        ("user", "première question"),
        ("assistant", "première réponse"),
    ]


def test_forgetting_twice_removes_two_exchanges(memory) -> None:
    """Cyril peut avoir insisté deux fois avant de constater le problème."""
    for i in range(3):
        memory.save_message("user", f"question {i}")
        memory.save_message("assistant", f"réponse {i}")

    memory.forget_last_exchange()
    memory.forget_last_exchange()

    assert memory.load_history() == [("user", "question 0"), ("assistant", "réponse 0")]


def test_forgetting_an_empty_history_is_harmless(memory) -> None:
    assert memory.forget_last_exchange() == 0
    assert memory.load_history() == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
