# conftest.py — règles valables pour TOUTE la suite de tests
#
# ⚠️ Pourquoi ce fichier existe (05/08/2026)
# ------------------------------------------
# Mesuré ce jour-là, en pointant `OLLAMA_HOST` vers un port mort :
#
#   Ollama vivant  : 1120 passés en  35 s
#   Ollama injoignable : 11 échoués, 1109 passés en 452 s
#
# Autrement dit, une partie de la suite « unitaire » dépendait
# silencieusement d'un service externe vivant — et devenait 13 fois plus
# lente quand il ne répondait pas, chaque appel attendant un timeout de
# connexion. Un développeur aurait cru la suite bloquée.
#
# C'est le miroir exact du motif traqué depuis deux jours : au lieu de
# « vert alors que ça ne marche pas », on avait « rouge alors que le code
# est bon ». Les deux détruisent la même chose — la confiance dans ce que
# le vert veut dire.
#
# ⚠️ Cette mesure elle-même a d'abord été fausse : `OLLAMA_HOST` était
# codé en dur dans config.py, donc poser la variable d'environnement ne
# changeait rien et la première campagne ne mesurait rien du tout. La
# valeur est désormais surchargeable — et le contrôle « la surcharge
# est-elle effective ? » a été fait avant de conclure quoi que ce soit.

from collections.abc import Callable

import pytest


@pytest.fixture(autouse=True)
def _classifieur_deterministe(monkeypatch):
    """
    Aucun test unitaire ne parle à Ollama.

    Le classifieur d'intention (`core/intent.py`) est le seul point du
    code où une décision de routage passe par un appel réseau. Il possède
    déjà un repli déterministe sur mots-clés, prévu pour le cas où le
    modèle est indisponible : on force ce repli en rendant `None` depuis
    `_ask_classifier`, qui est exactement la frontière réseau.

    Ce que les tests continuent de vérifier : le ROUTAGE et l'injection
    de contexte, qui sont du code Python déterministe. Ce qu'ils ne
    vérifient plus, et qui n'était de toute façon pas leur affaire : la
    justesse du classifieur LLM lui-même — elle est mesurée là où c'est
    sa place, sur un corpus dédié, dans `test_intent.py`.

    ⚠️ `test_intent.py` pose son propre `_ask_classifier` par-dessus
    celui-ci, et doit continuer de le faire : c'est le seul fichier dont
    le sujet EST le classifieur.

    Le cache est vidé avant ET après : une classification obtenue d'un
    vrai modèle lors d'un test antérieur survivrait sinon à ce stub, et
    le rendrait silencieusement inopérant — précisément le genre de faux
    négatif que ce fichier existe pour empêcher.
    """
    from core import intent

    intent._CACHE.clear()
    monkeypatch.setattr(intent, "_ask_classifier", lambda question, context="": None)
    yield
    intent._CACHE.clear()


def event_recorder() -> tuple[list[tuple[str, str]], Callable[[str, str], None]]:
    """Un enregistreur d'événements typé, pour remplacer les lambdas.

    ⚠️ Pourquoi une fonction nommée plutôt qu'une lambda (06/08/2026)

    Quatorze appels de la suite écrivaient
    `log_event=lambda t, d="": events.append((t, d))`. Le code de
    production déclare pourtant le bon type —
    `Callable[[str, str], None] | None`. C'est mypy qui abandonne :
    face à un type UNION, il ne sait pas contre quel membre vérifier
    une lambda, et rend « Cannot infer type of lambda ».

    Le correctif ne pouvait donc pas venir de la production, dont le
    type est déjà juste. Une fonction nommée, elle, est inférée seule,
    indépendamment de l'union.

    Usage :
        events, log_event = event_recorder()
        Guardian(log_event=log_event).scan()
        assert [t for t, _ in events] == ["security_..."]
    """
    events: list[tuple[str, str]] = []

    def log_event(event_type: str, details: str = "") -> None:
        events.append((event_type, details))

    return events, log_event
