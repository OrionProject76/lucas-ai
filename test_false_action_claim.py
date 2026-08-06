# test_false_action_claim.py — Luca's ne doit jamais confirmer une action
# qui n'a pas eu lieu.
#
# Régression réelle du 05/08/2026 (PWA mobile, Cyril) :
#   Cyril    : « Bonjour , ouvre le bloc note »
#   Luca's   : « D'accord, j'ouvrirai donc le Bloc-notes sur votre PC.
#                Le Bloc-notes est lancé. »
#   Réalité  : aucun Bloc-notes ouvert, aucune entrée dans action_log —
#              l'action n'avait même pas été TENTÉE.
#
# Deux défauts distincts derrière ce seul symptôme, testés séparément :
#   1. le déclencheur ne reconnaissait pas « bloc note » (singulier) ;
#   2. rien n'empêchait le modèle d'affirmer un succès quand aucune action
#      n'avait été exécutée.
#
# Le second est le vrai sujet : corriger 1 seul aurait laissé la faille
# entière pour toute autre formulation non reconnue.

import pytest

from core.lucas_core import FALSE_CLAIM_CORRECTION, claims_action_success
from core.router import extract_app_name, looks_like_app_request, should_use_automation

# ── 1. Le déclencheur : variantes d'écriture d'un même nom ─────────────


def test_the_exact_phrase_cyril_typed_is_recognized() -> None:
    """La phrase réelle, telle quelle — apostrophe, espace parasite compris."""
    assert extract_app_name("Bonjour , ouvre le bloc note") == "notepad"


@pytest.mark.parametrize(
    "phrase",
    [
        "ouvre le bloc note",     # singulier — celle qui a échoué
        "ouvre le bloc-note",
        "ouvre le bloc notes",
        "ouvre le bloc-notes",
        "ouvre notepad",
        "lance le bloc note",
    ],
)
def test_notepad_variants_all_resolve(phrase: str) -> None:
    assert extract_app_name(phrase) == "notepad"


def test_elided_article_is_handled() -> None:
    """
    « ouvre l'explorateur » : l'article élidé n'est pas suivi d'un espace.
    Trouvé en vérifiant le correctif « bloc note », pas en usage réel —
    même classe de bug, une variante d'écriture naturelle qui ne
    déclenchait rien.
    """
    assert extract_app_name("ouvre l'explorateur") == "explorer"


@pytest.mark.parametrize(
    "phrase",
    [
        "lance une reflexion sur Chrome",   # faux positif documenté
        "parle-moi du bloc note",          # pas de verbe d'ouverture
        "comment ouvrir un fichier",       # question, pas demande d'action
    ],
)
def test_no_launch_without_a_real_request(phrase: str) -> None:
    assert extract_app_name(phrase) is None
    assert should_use_automation(phrase) is False


# ── 2. « Une action a été demandée » vs « on sait la faire » ───────────


@pytest.mark.parametrize("phrase", ["ouvre spotify", "lance photoshop", "ouvre le tableur"])
def test_unknown_app_is_still_detected_as_a_request(phrase: str) -> None:
    """
    C'est CE trou qui a produit la fausse confirmation : application non
    reconnue → aucun bloc de contexte injecté → le modèle inventait. La
    demande doit être détectée même quand elle est inexécutable.
    """
    assert looks_like_app_request(phrase) is True
    assert should_use_automation(phrase) is False


@pytest.mark.parametrize(
    "phrase",
    ["quelle heure est-il", "lance une recherche", "ouvre la discussion", "comment ouvrir un fichier"],
)
def test_broad_detection_does_not_fire_on_everything(phrase: str) -> None:
    assert looks_like_app_request(phrase) is False


# ── 3. Le garde-fou déterministe ──────────────────────────────────────
#
# Pourquoi pas seulement une consigne de prompt : §5.29 a mesuré qu'une
# règle du prompt système tombe à 2/9 sous 100 messages d'historique. Une
# affirmation sur l'état réel de la machine de Cyril ne peut pas reposer
# là-dessus.


@pytest.mark.parametrize(
    "reponse",
    [
        "Le Bloc-notes est lancé. Comment puis-je vous aider ?",
        "D'accord, j'ouvrirai donc le Bloc-notes sur votre PC.\n\nLe Bloc-notes est lancé.",
        "J'ai ouvert le Bloc-notes.",
        "Le bloc-notes a été lancé sur votre PC.",
        "Je viens d'ouvrir Chrome.",
        "La calculatrice est maintenant ouverte.",
    ],
)
def test_success_claims_are_detected(reponse: str) -> None:
    assert claims_action_success(reponse) is True


@pytest.mark.parametrize(
    "reponse",
    [
        "Je vais ouvrir le Bloc-notes.",            # intention, pas état
        "Veux-tu que j'ouvre le Bloc-notes ?",
        "Je ne peux pas ouvrir cette application.",
        "Désolé, Spotify ne fait pas partie des applications autorisées.",
        "Voici la météo à Paris.",
    ],
)
def test_honest_answers_are_left_alone(reponse: str) -> None:
    """
    Une intention annoncée n'est pas un mensonge sur ce qui s'est passé :
    la corriger ajouterait du bruit sur des réponses correctes.
    """
    assert claims_action_success(reponse) is False


def test_the_correction_states_plainly_that_nothing_ran() -> None:
    """
    Le texte ajouté doit être sans ambiguïté pour Cyril : c'est lui qui
    lira l'écart entre ce que Luca's a écrit et ce qui s'est passé.
    """
    assert "aucune action" in FALSE_CLAIM_CORRECTION.lower()
    assert "rien n'a été lancé" in FALSE_CLAIM_CORRECTION.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
