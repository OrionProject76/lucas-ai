# test_detecteurs_multi_modeles.py — les détecteurs face à DEUX modèles
#
# ⚠️ Ce que cet épisode a montré (05/08/2026, ROADMAP.md §5.47)
# ---------------------------------------------------------------------
# `claims_action_success()` et `is_vision_refusal()` sont des expressions
# régulières écrites en observant qwen2.5:7b. Après la bascule sur
# gpt-oss:20b, mesurées sur les formulations réelles du nouveau modèle :
#
#     claims_action_success : 1/6 puis 0/6
#     is_vision_refusal     : 0/6
#
# Les deux garde-fous étaient devenus **entièrement aveugles**, sans
# qu'aucun test ne le signale — parce qu'aucun test ne confrontait ces
# motifs au vocabulaire d'un modèle qui n'existait pas quand ils ont été
# écrits. Un détecteur qui cesse de détecter ne produit aucune erreur : il
# redevient silencieux, ce qui est le pire mode de défaillance pour un
# mécanisme dont la raison d'être est de rattraper un mensonge.
#
# Les chaînes ci-dessous sont RECOPIÉES TELLES QUELLES depuis la sortie
# des deux modèles, apostrophes typographiques et espaces fines
# comprises. C'est le point : une phrase reformulée « proprement » par un
# humain ne teste plus rien.
#
# ⚠️ Ce fichier a une limite qu'il faut connaître : il fige le vocabulaire
# de DEUX modèles à une date. Il ne garantit rien sur le prochain. La
# seule parade réelle est de rejouer cette confrontation à chaque
# changement de modèle — pas d'espérer que les motifs soient devenus
# universels.

from __future__ import annotations

import pytest

from core.lucas_core import claims_action_success, is_vision_refusal

# ── Fausses confirmations d'action ────────────────────────────────────


@pytest.mark.parametrize(
    "reponse",
    [
        # qwen2.5:7b
        "Le Bloc-notes est lancé. Comment puis-je vous aider ?",
        "J'ai ouvert le Bloc-notes.",
        "Le bloc-notes a été lancé sur votre PC.",
        # gpt-oss:20b — participe SEUL, sans verbe : la forme qu'aucun
        # motif construit autour d'un verbe ne pouvait attraper.
        "Bloc‑notes ouvert sur ton PC.",
        "Bloc‑notes lancé sur ton PC, tu peux commencer.",
        # gpt-oss:20b — « déjà », absent de la liste d'adverbes d'origine
        "Le Bloc‑notes est déjà lancé sur ton PC.",
        # gpt-oss:20b — tournures nouvelles
        "Salut Cyril ! Le Bloc‑notes vient tout juste de s’ouvrir sur ton PC.",
        "Le Bloc‑Notes vient de démarrer sur ton PC, Cyril.",
        "J’ai mis le Bloc‑Notes en marche sur ton PC.",
        "Coucou Cyril ! Ton bloc-notes vient d’être ouvert sur ton PC.",
    ],
)
def test_a_success_claim_is_detected(reponse: str) -> None:
    assert claims_action_success(reponse)


@pytest.mark.parametrize(
    "reponse",
    [
        "Je vais ouvrir le Bloc-notes.",          # intention, pas état
        "Tu veux que je l’ouvre ?",
        "Spotify n’est pas parmi les applications que je peux ouvrir sur ton PC.",
        "Il est 12 h 30.",
        # Piège : « ouvert » présent, mais il parle d'un fichier, pas
        # d'une action de Luca. C'est pourquoi le motif « participe seul »
        # exige un nom d'application juste avant.
        "Le fichier ouvert dans ton éditeur contient du Python.",
    ],
)
def test_an_honest_answer_is_left_alone(reponse: str) -> None:
    assert not claims_action_success(reponse)


# ── Refus de vision ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "reponse",
    [
        # qwen2.5:7b
        "Je n'ai pas accès à l'écran de votre ordinateur.",
        # gpt-oss:20b — chaque ligne ratée par les motifs d'origine
        "Je ne peux pas voir ce qu’il y a à ton écran, désolé.",
        "Cyril, je n’ai malheureusement aucun moyen de voir ce qu’il y a affiché sur ton écran.",
        "Cyril, je n’ai aucun accès à ton écran ; je ne peux donc pas voir ce qu’il y a affiché.",
        "Je n’arrive pas à voir ton écran Cyril, sans accès je suis totalement dans le flou.",
        "Hé Cyril, je n’ai aucune manière de voir ce qui se passe sur ton écran.",
        "Hélas, je ne vois rien de ton écran, alors pas d’indication à donner.",
        "Salut Cyril, je n'arrive vraiment pas à voir ce qu'il y a sur ton écran.",
        "Désolé Cyril, mais je n’ai aucune visibilité sur ce qui s’affiche sur ton écran.",
    ],
)
def test_a_vision_refusal_is_detected(reponse: str) -> None:
    assert is_vision_refusal(reponse)


@pytest.mark.parametrize(
    "reponse",
    [
        "Voici ce que je lis à l'écran : une erreur de compilation Python.",
        "Il est 12 h 30.",
        "J'ai ouvert le Bloc-notes.",
    ],
)
def test_a_real_answer_is_not_taken_for_a_refusal(reponse: str) -> None:
    """
    Un vrai compte rendu d'écran filtré comme un refus disparaîtrait de
    l'historique — Luca perdrait ce qu'elle vient de lire.
    """
    assert not is_vision_refusal(reponse)


# ── La leçon, verrouillée ─────────────────────────────────────────────


def test_typographic_characters_do_not_defeat_the_detectors() -> None:
    """
    gpt-oss écrit « Bloc‑notes » (U+2011) et « Cyril ! » (U+202F). Sans
    le repli typographique de normalize(), ces deux détecteurs — et la
    garde de sécurité is_sensitive() — redeviennent aveugles.
    Voir test_typographie_securite.py.
    """
    assert claims_action_success("Bloc‑notes ouvert sur ton PC.")
    assert is_vision_refusal("Je ne peux pas voir ton écran.")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
