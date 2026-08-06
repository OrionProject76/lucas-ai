# test_lucas_core_mutants.py — les 11 survivants du chef d'orchestre
#
# ⚠️ Pourquoi ce fichier existe (06/08/2026)
# ------------------------------------------
# Suite de la campagne de mutation (605 mutants, 86 survivants). Après
# `security/`, `core/lucas_core.py` est le module où un survivant coûte le
# plus cher : c'est lui qui décide ce qui part au cloud, ce qui déclenche
# une capture d'écran, et si une réponse a le droit d'affirmer qu'une
# action a eu lieu.
#
# Quatre des onze touchent directement une garantie de confiance :
#   451  la vision ne se déclenche JAMAIS sur une question cloud
#   846  le témoin d'action est remis à zéro à chaque tour
#   875  une action réellement exécutée lève bien ce témoin
#   1297 sans témoin, une fausse confirmation est corrigée
#
# Les autres protègent la qualité de ce que Cyril lit.

from __future__ import annotations

import pytest

from core.lucas_core import LucasCore, fit_history_to_budget
from test_memory_double import MemoryDouble

# ══ 125 — la troncature coupe sur un mot, jamais au milieu ════════════

def test_a_truncated_message_is_cut_on_a_word_boundary() -> None:
    """
    ⚠️ Ce n'est pas de l'esthétique. La docstring de `fit_history_to_budget`
    le documente : tout motif régulier ajouté à l'historique devient un
    exemple que le modèle IMITE. Une coupe en plein mot lui apprend à
    couper ses propres réponses en plein mot — mesuré en réel.

    Mutant : `espace > limit // 2` -> `<=`. Inversé, la coupe tombe
    n'importe où.
    """
    # ⚠️ Un mot LONG, délibérément. Avec « mot », la coupe tombe pile sur
    # un espace et la mutation devient ÉQUIVALENTE : les deux branches
    # rendent le même texte, et le test ne prouve rien. Vérifié en
    # comparant les deux sorties caractère par caractère.
    long_message = "anticonstitutionnellement " * 20
    # ⚠️ `recent_max_chars` ET `max_chars` : le dernier échange garde une
    # limite plus généreuse (les questions elliptiques n'ont de sens que
    # par rapport à lui). Ne borner que `max_chars` laissait ce message
    # unique à 599 caractères — le test ne mesurait rien.
    [(_role, contenu)] = fit_history_to_budget(
        [("user", long_message)], budget=10_000, max_chars=100, recent_max_chars=100
    )

    assert len(contenu) <= 100
    # Chaque morceau doit être le mot ENTIER : un fragment signale une
    # coupe au mauvais endroit.
    assert all(m == "anticonstitutionnellement" for m in contenu.split()), (
        f"fragment de mot en fin de troncature : {contenu[-30:]!r}"
    )


# ══ La chaîne de confiance sur les actions ════════════════════════════

class _MemoireAction(MemoryDouble):
    def __init__(self) -> None:
        super().__init__()
        self.actions: list[dict] = []
        self.messages: list[tuple[str, str]] = []

    def save_action(self, action, source, result):
        self.actions.append({"action": action, "source": source, "result": result})

    def save_message(self, role, texte):
        self.messages.append((role, texte))


def _core(monkeypatch, reponse: str) -> tuple[LucasCore, _MemoireAction]:
    """Un LucasCore sans base ni LLM, dont la réponse est imposée."""
    import core.lucas_core as lc

    instance = LucasCore.__new__(LucasCore)
    memoire = _MemoireAction()
    instance.memory = memoire  # type: ignore[assignment]  # double assumé, voir test_memory_double.py
    instance.log_event = lambda event_type, details="": None  # type: ignore[method-assign]

    monkeypatch.setattr(lc, "route", lambda message, contexte="": "local")
    monkeypatch.setattr(lc, "ask_local", lambda messages: reponse)
    monkeypatch.setattr(
        lc.LucasCore, "_build_messages",
        lambda self, *a, **k: [{"role": "user", "content": "peu importe"}],
    )
    monkeypatch.setattr(lc.LucasCore, "recent_context", lambda self: "")
    return instance, memoire


def test_a_claim_of_success_is_corrected_when_no_action_ran(monkeypatch) -> None:
    """
    Mutant 1297 : `getattr(self, "_action_executed", False)` -> `True`.
    Avec `True` par défaut, une instance sans témoin serait crue sur
    parole — et la fausse confirmation passerait.
    """
    from core.lucas_core import FALSE_CLAIM_CORRECTION

    instance, memoire = _core(monkeypatch, "Le Bloc-notes est lancé.")
    # Le témoin n'existe PAS : c'est le cas que le défaut de getattr couvre.
    assert not hasattr(instance, "_action_executed")

    reponse = instance.ask("ouvre le bloc note")
    assert FALSE_CLAIM_CORRECTION in reponse
    assert memoire.actions[0]["result"] == "false_claim_corrected"


def test_a_real_action_is_confirmed_without_being_corrected(monkeypatch) -> None:
    """
    Le miroir, et il compte autant : quand l'action a VRAIMENT eu lieu,
    ajouter un démenti serait tout aussi mensonger — et apprendrait à
    Cyril à ne plus croire les corrections.

    Mutant 875 : `self._action_executed = True` -> `False`.
    """
    from core.lucas_core import FALSE_CLAIM_CORRECTION

    instance, memoire = _core(monkeypatch, "Le Bloc-notes est lancé.")
    instance._action_executed = True

    reponse = instance.ask("ouvre le bloc note")
    assert FALSE_CLAIM_CORRECTION not in reponse, (
        "une action réellement exécutée ne doit pas être démentie"
    )
    assert not any(a["result"] == "false_claim_corrected" for a in memoire.actions)


def test_the_action_witness_is_reset_at_every_turn(monkeypatch) -> None:
    """
    ⚠️ Mutant 846 : `self._action_executed = False` -> `True`.

    Le témoin doit repartir à zéro à CHAQUE construction de prompt. S'il
    restait vrai d'un tour sur l'autre, une action réussie au tour 1
    autoriserait une fausse confirmation au tour 2 — exactement la faille
    que ce mécanisme ferme (ROADMAP.md §5.31).
    """
    import core.lucas_core as lc

    instance = LucasCore.__new__(LucasCore)
    instance.memory = _MemoireAction()  # type: ignore[assignment]  # double assumé
    instance.log_event = lambda event_type, details="": None  # type: ignore[method-assign]
    instance._action_executed = True  # résidu d'un tour précédent

    monkeypatch.setattr(lc, "route", lambda message, contexte="": "local")
    monkeypatch.setattr(lc.LucasCore, "recent_context", lambda self: "")
    instance._build_messages("bonjour", "local")

    assert instance._action_executed is False, (
        "le témoin doit être remis à zéro, sinon un tour contamine le suivant"
    )


# ══ 451 — la vision ne se déclenche jamais sur une question cloud ═════

def test_a_cloud_question_never_triggers_a_screen_capture(monkeypatch) -> None:
    """
    ⚠️ Garde de sécurité, pas d'optimisation. Une capture d'écran envoyée
    au cloud exposerait ce que Cyril a sous les yeux. Le routage cloud et
    la vision sont donc mutuellement exclusifs.

    Mutant 451 : `not is_cloud and VISION_ENABLED` -> `or`. Avec `or`,
    une question cloud déclenchait la capture dès que la vision est
    activée.
    """
    import core.lucas_core as lc

    monkeypatch.setattr(lc, "VISION_ENABLED", True)

    def _interdit(*a, **k):
        raise AssertionError("aucune capture ne doit être déclenchée en cloud")

    monkeypatch.setattr(lc.LucasCore, "_describe_screen", _interdit)
    monkeypatch.setattr(lc.LucasCore, "_describe_camera_image", _interdit)

    instance = LucasCore.__new__(LucasCore)
    instance.memory = MemoryDouble()  # type: ignore[assignment]  # double assumé
    instance.log_event = lambda event_type, details="": None  # type: ignore[method-assign]

    instance._build_messages(
        "analyse ce qui est à l'écran", "cloud", image_path="photo.png"
    )


# ══ 966 — filtrer les refus de vision, pas tout l'historique ══════════

def test_only_vision_refusals_are_dropped_from_history(monkeypatch) -> None:
    """
    Quand la vision se déclenche, les anciens « je ne vois pas ton écran »
    sont retirés de l'historique : les garder apprendrait au modèle à
    refuser de nouveau.

    Mutant 966 : `role == "assistant" and is_vision_refusal(content)` ->
    `or`. Avec `or`, TOUS les messages assistants disparaissaient — Luca's
    perdait le fil de la conversation dès qu'elle regardait l'écran.
    """
    import core.lucas_core as lc

    class _Memoire(MemoryDouble):
        def load_history(self):
            return [
                ("user", "et pour 2024 ?"),
                ("assistant", "Le total est de 1847 euros."),
            ]

        def load_history_with_metadata(self):
            return [
                {"role": r, "message": m, "confidence": 1.0,
                 "importance": 0.5, "expiration": None}
                for r, m in self.load_history()
            ]

    monkeypatch.setattr(lc, "VISION_ENABLED", True)
    monkeypatch.setattr(
        lc.LucasCore, "_describe_screen",
        lambda self, *a, **k: "Texte lu à l'écran : un tableau",
    )
    monkeypatch.setattr(lc, "is_vision_refusal", lambda contenu: False)

    instance = LucasCore.__new__(LucasCore)
    instance.memory = _Memoire()  # type: ignore[assignment]  # double assumé
    instance.log_event = lambda event_type, details="": None  # type: ignore[method-assign]

    messages = instance._build_messages("regarde mon écran", "local")
    assert any("1847" in m["content"] for m in messages), (
        "un message assistant qui n'est PAS un refus doit rester dans l'historique"
    )


# ══ 1326 — la question courante n'est pas son propre contexte ═════════

def test_the_current_question_is_not_used_as_its_own_context() -> None:
    """
    `recent_context()` sert au classifieur d'intention. Se donner sa
    propre question comme « échange précédent » n'aurait aucun sens et
    fausserait la classification.

    Mutant 1326 : `history[-1][0] == "user"` -> `!=`.
    """
    class _Memoire(MemoryDouble):
        def load_history(self):
            return [
                ("user", "quel est le total ?"),
                ("assistant", "1847 euros."),
                ("user", "et pour 2024 ?"),  # la question EN COURS
            ]

    instance = LucasCore.__new__(LucasCore)
    instance.memory = _Memoire()  # type: ignore[assignment]  # double assumé

    contexte = instance.recent_context()
    assert "et pour 2024" not in contexte, (
        "la question en cours doit être exclue de son propre contexte"
    )
    assert "1847" in contexte, "l'échange précédent, lui, doit être présent"


# ══ 1256 — la capture d'écran est autorisée par défaut ════════════════

def test_screen_capture_is_allowed_by_default() -> None:
    """
    `allow_screen_capture: bool = True` : l'UI bureau ne passe pas ce
    paramètre, seul le pont mobile le met à False (le téléphone ne doit
    pas déclencher une capture du PC sans le dire).

    Mutant 1256 : le défaut passe à `False` — la vision cesserait de
    fonctionner depuis le bureau, en silence.
    """
    import inspect

    signature = inspect.signature(LucasCore.ask)
    assert signature.parameters["allow_screen_capture"].default is True


# ══ 1232 — la consigne « texte seul » n'apparaît que sans description ══

def test_the_text_only_instruction_appears_when_the_vlm_is_silent() -> None:
    """
    Quand l'OCR a du texte mais que le VLM n'a rien produit (v1.0 : il est
    coupé), une consigne dit au modèle de s'appuyer sur le texte seul.

    Formulée comme une consigne et non comme une panne : annoncer un échec
    pousserait le modèle à se dédire alors qu'il a le texte sous les yeux.

    Mutant 1232 : `screen_text and not visual` -> `or`. Avec `or`, la
    consigne apparaissait AUSSI quand le VLM avait décrit la scène — Luca's
    s'interdisait alors d'utiliser une description qu'elle possédait.
    """
    instance = LucasCore.__new__(LucasCore)
    CONSIGNE = "appuie-toi sur le texte seul"

    avec_texte_seul = instance._compose_vision_block("un tableau de chiffres", "")
    assert CONSIGNE in avec_texte_seul

    avec_les_deux = instance._compose_vision_block(
        "un tableau de chiffres", "une fenêtre Excel plein écran"
    )
    assert CONSIGNE not in avec_les_deux, (
        "avec une description disponible, la consigne « texte seul » serait fausse"
    )


# ══ 457 / 472 — le message d'activité dit ce qui a VRAIMENT été lu ════

@pytest.mark.parametrize(
    ("description", "attendu", "exclu"),
    [
        ("Texte lu à l'écran : total 1847", "texte trouvé", "rien d'exploitable"),
        ("Contexte visuel seulement", "rien d'exploitable", "texte trouvé"),
    ],
)
def test_the_activity_message_reflects_what_was_actually_read(
    monkeypatch, description: str, attendu: str, exclu: str
) -> None:
    """
    Le bandeau d'activité annonce à Cyril ce que la capture a donné. S'il
    dit « texte trouvé » alors que l'OCR n'a rien lu, il ment sur une
    opération qui a lu son écran — le pire endroit pour se tromper.

    Mutants 457 et 472 : `"Texte lu à l'écran" in vision_context` ->
    `not in`. Inversés, les deux messages s'échangent.
    """
    import core.lucas_core as lc

    monkeypatch.setattr(lc, "VISION_ENABLED", True)
    monkeypatch.setattr(
        lc.LucasCore, "_describe_camera_image", lambda self, *a, **k: description
    )

    instance = LucasCore.__new__(LucasCore)
    instance.memory = MemoryDouble()  # type: ignore[assignment]  # double assumé
    instance.log_event = lambda event_type, details="": None  # type: ignore[method-assign]

    activites: list[tuple[str, str]] = []
    instance._build_messages(
        "que vois-tu ?", "local", image_path="photo.png",
        on_activity=lambda genre, texte: activites.append((genre, texte)),
    )

    lus = [texte for genre, texte in activites if genre == "screen_read"]
    assert lus, "une lecture d'écran doit être annoncée"
    assert attendu in lus[0]
    assert exclu not in lus[0]


# ══ 875 — le témoin est levé par le VRAI chemin d'exécution ═══════════

def test_a_real_launch_raises_the_action_witness(monkeypatch) -> None:
    """
    ⚠️ Ma première version posait `_action_executed = True` à la main —
    elle sautait donc la ligne même qu'elle prétendait protéger, et le
    mutant survivait.

    Ici le témoin est levé par la CHAÎNE RÉELLE : résolution du nom
    d'application, décision, exécution.

    Mutant 875 : `self._action_executed = True` -> `False`. Inversé, une
    action réellement lancée serait ensuite démentie par le garde-fou anti
    fausse confirmation — Luca's nierait ce qu'elle vient de faire.
    """
    import core.lucas_core as lc

    class _Automation:
        def __init__(self, log_event=None):
            self.lancees: list[str] = []

        def open_app(self, nom):
            self.lancees.append(nom)
            return f"{nom} lancé"

    monkeypatch.setattr("modules.automation_manager.AutomationManager", _Automation)

    instance = LucasCore.__new__(LucasCore)
    instance.memory = _MemoireAction()  # type: ignore[assignment]  # double assumé
    instance.log_event = lambda event_type, details="": None  # type: ignore[method-assign]
    monkeypatch.setattr(lc.LucasCore, "recent_context", lambda self: "")

    instance._build_messages("ouvre notepad", "local")

    assert instance._action_executed is True, (
        "une action réellement exécutée doit lever le témoin, "
        "sinon la confirmation légitime sera démentie"
    )


@pytest.mark.parametrize(
    ("description", "attendu", "exclu"),
    [
        ("Texte lu à l'écran : total 1847", "texte trouvé", "rien d'exploitable"),
        ("Contexte visuel seulement", "rien d'exploitable", "texte trouvé"),
    ],
)
def test_the_screen_activity_message_reflects_what_was_read(
    monkeypatch, description: str, attendu: str, exclu: str
) -> None:
    """
    Le pendant du test précédent pour la CAPTURE D'ÉCRAN (ligne 472), et
    non la photo du téléphone (ligne 457).

    ⚠️ Les deux chemins portent la même condition, écrite deux fois. Ne
    tester que l'un laissait l'autre mutant survivre — un test par
    chemin, pas un test par formulation.
    """
    import core.lucas_core as lc

    monkeypatch.setattr(lc, "VISION_ENABLED", True)
    monkeypatch.setattr(lc, "should_use_vision", lambda message, contexte="": True)
    monkeypatch.setattr(
        lc.LucasCore, "_describe_screen", lambda self, *a, **k: description
    )

    instance = LucasCore.__new__(LucasCore)
    instance.memory = MemoryDouble()  # type: ignore[assignment]  # double assumé
    instance.log_event = lambda event_type, details="": None  # type: ignore[method-assign]

    activites: list[tuple[str, str]] = []
    instance._build_messages(
        "regarde mon écran", "local",
        on_activity=lambda genre, texte: activites.append((genre, texte)),
    )

    lus = [texte for genre, texte in activites if genre == "screen_read"]
    assert lus, "une lecture d'écran doit être annoncée"
    assert attendu in lus[0]
    assert exclu not in lus[0]
