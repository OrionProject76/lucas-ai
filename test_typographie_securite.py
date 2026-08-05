# test_typographie_securite.py — la typographie ne doit pas contourner
# une garde de sécurité
#
# ⚠️ Faille RÉELLE trouvée le 05/08/2026, après la bascule sur
# gpt-oss:20b (ROADMAP.md §5.47)
# ---------------------------------------------------------------------
# Ce modèle écrit avec de la vraie typographie française : espace fine
# insécable avant « ! » et « ? » (U+202F), trait d'union insécable dans
# « Bloc‑notes » (U+2011). Ni l'un ni l'autre n'est le caractère ASCII
# correspondant.
#
# Mesuré AVANT correctif :
#
#     is_sensitive("mon compte bancaire")       -> True
#     is_sensitive("mon compte bancaire")  -> False   ⚠️
#     route_voice("Ton compte bancaire…")  -> "cloud" ⚠️
#
# `route_voice()` analyse la RÉPONSE du modèle pour décider si le texte
# part chez Microsoft (edge_tts) ou reste local (Piper). Le modèle
# pouvait donc, par sa seule typographie, faire sortir de la machine une
# donnée bancaire.
#
# Ces tests existent pour qu'un futur changement de modèle — ou une
# « simplification » de normalize() — ne rouvre pas ce chemin.

from __future__ import annotations

import pytest

from core.router import is_sensitive, route_voice
from core.text_utils import contains_any, normalize

FINE = " "      # espace fine insécable — utilisée par gpt-oss:20b
NBSP = " "      # espace insécable
CADRATIN = "—"  # tiret cadratin
INSEC = "‑"     # trait d'union insécable — utilisé par gpt-oss:20b


# ── normalize() replie les catégories, pas une liste de caractères ────


@pytest.mark.parametrize("espace", [FINE, NBSP, " ", " ", "　"])
def test_every_unicode_space_becomes_a_plain_space(espace: str) -> None:
    """
    Repli par CATÉGORIE (Zs), pas par liste. Une liste nommant U+202F et
    U+00A0 aurait corrigé les cas connus et laissé passer le suivant — et
    on ne sait pas quelle typographie le prochain modèle emploiera.
    """
    assert normalize(f"compte{espace}bancaire") == "compte bancaire"


@pytest.mark.parametrize("tiret", [INSEC, "‐", "–", CADRATIN, "−"])
def test_every_unicode_dash_becomes_a_plain_hyphen(tiret: str) -> None:
    assert normalize(f"bloc{tiret}notes") == "bloc-notes"


def test_accents_and_apostrophes_still_work() -> None:
    """Non-régression : le comportement d'origine est intact."""
    assert normalize("Qu’est-ce que l'ÉCRAN ?") == "qu'est-ce que l'ecran ?"


# ── La faille elle-même, dans les deux sens ───────────────────────────


@pytest.mark.parametrize("espace", [FINE, NBSP])
def test_a_sensitive_keyword_survives_a_typographic_space(espace: str) -> None:
    assert is_sensitive(f"mon compte{espace}bancaire")
    assert is_sensitive(f"mon mot{espace}de{espace}passe")


def test_sensitive_content_stays_local_whatever_the_typography() -> None:
    """
    LE test de la faille. Une réponse annonçant un solde bancaire ne doit
    jamais partir chez Microsoft, quelle que soit la façon dont le modèle
    a tapé ses espaces.
    """
    for espace in (" ", FINE, NBSP):
        reponse = f"Ton compte{espace}bancaire affiche 3200 euros."
        assert route_voice(reponse, "et mon solde ?") == "local", (
            f"contenu sensible routé vers le cloud avec {espace!r}"
        )


def test_an_ordinary_answer_still_goes_to_the_better_voice() -> None:
    """
    Garde-fou symétrique : le correctif ne doit pas tout forcer en local.
    edge_tts reste le défaut sur du contenu anodin (CLAUDE.md, TTS).
    """
    assert route_voice("Il est 12 h 30.", "quelle heure est-il ?") == "cloud"


# ── Le déclencheur d'action aussi ─────────────────────────────────────


def test_an_app_name_with_a_non_breaking_hyphen_is_recognized() -> None:
    """
    gpt-oss écrit « Bloc‑notes » avec U+2011. Sans le repli, la demande
    d'ouverture ne déclenchait plus rien — et §5.31 a montré ce que
    produit un déclencheur muet : le modèle affirme avoir agi.
    """
    from core.router import extract_app_name

    assert extract_app_name(f"ouvre le bloc{INSEC}notes") == "notepad"


def test_contains_any_normalizes_both_sides() -> None:
    assert contains_any(f"mon relevé{FINE}bancaire", ["relevé bancaire"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
