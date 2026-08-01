# test_intent.py — le corpus de formulations réelles
#
# ── À quoi sert ce fichier ────────────────────────────────────────────
#
# C'est lui, et non le classifieur, qui répond à la demande de Cyril
# d'arrêter de corriger « au cas par cas ».
#
# Chaque formulation qui échoue en usage réel vient s'ajouter à CORPUS
# ci-dessous, avec la date et ce qui s'est passé. Ce qui est mesuré est
# alors le score GLOBAL, pas le cas isolé : une correction qui répare une
# formulation en cassant deux autres devient visible immédiatement, au
# lieu de se découvrir trois semaines plus tard.
#
# ── Deux niveaux de test ──────────────────────────────────────────────
#
# Les tests unitaires (par défaut) ne touchent pas à Ollama : le
# classifieur est remplacé par un faux. Ils vérifient le câblage,
# l'exclusivité des labels et le repli.
#
# Le test de couverture (marqué `integration`, exclu par pytest.ini)
# interroge le vrai modèle et affiche le score. C'est le seul qui mesure
# la qualité réelle :
#     venv\Scripts\python.exe -m pytest test_intent.py -m integration -v -s

from __future__ import annotations

import pytest

from core import intent
from core.intent import DOCUMENTS, NEITHER, SCREEN, Intent, classify

# ── Le corpus ─────────────────────────────────────────────────────────
#
# (question, attendu, origine)
#
# « origine » dit d'où vient le cas : une formulation tapée par Cyril qui
# a échoué, ou un témoin ajouté pour vérifier qu'on ne déclenche pas à
# tort. Sans cette colonne, on ne sait plus dans six mois pourquoi une
# ligne est là, et on la « corrige » en croyant bien faire.

CORPUS: list[tuple[str, str, str]] = [
    # — Échecs réels, conversation du 01/08/2026 ————————————————
    ("qu’est ce que tu vois à l’écran ?", SCREEN,
     "01/08 — apostrophe typographique, corrigé par text_utils"),
    ("qu'est ce que tu vois a l'ecran", SCREEN,
     "01/08 — sans accents, corrigé par text_utils"),
    ("Je voudrais une synthèse rapide d'un document sur mon écran", SCREEN,
     "01/08 — RAG et vision déclenchaient ensemble, le RAG noyait la vision"),
    ("peux-tu lire ce qui est affiché", SCREEN,
     "01/08 — aucun mot-clé ne correspondait"),
    ("analyse ce document ouvert", SCREEN,
     "01/08 — partait vers le RAG ; « ce » désigne l'écran"),
    ("résume ce document", SCREEN,
     "01/08 — même motif, résiste aux 3 modèles ; garde déictique"),
    ("c'est quoi ces chiffres", SCREEN,
     "01/08 — déixis au pluriel"),
    ("c'est écrit quoi ?", SCREEN,
     "01/08 — elliptique, hors de portée des mots-clés"),
    ("j'ai un message d'erreur, aide-moi", SCREEN,
     "01/08 — l'écran est implicite, jamais nommé"),
    ("montre-moi ce qu'il y a marqué là", SCREEN,
     "01/08 — deixis pure"),

    # — Formulations qui marchaient déjà : ne pas les casser ——————
    ("regarde mon écran", SCREEN, "témoin — cas nominal"),
    ("qu'est-ce que tu vois sur cette fenêtre", SCREEN, "témoin"),
    ("aide-moi avec cette erreur", SCREEN, "témoin"),

    # — Vrais cas RAG : le classifieur ne doit pas tout envoyer à l'écran —
    ("résume mon rapport annuel", DOCUMENTS, "témoin — vrai RAG"),
    ("que dit le document sur les congés", DOCUMENTS, "témoin — vrai RAG"),
    ("rappelle-moi ce que contient mon contrat d'assurance", DOCUMENTS,
     "témoin — vrai RAG, nomme le document sans rien montrer"),

    # — Ni l'un ni l'autre : déclencher ici coûte plusieurs secondes ——
    ("regarde si tu peux m'aider", NEITHER,
     "01/08 — verbe de perception idiomatique ; le classifieur y tombait, "
     "corrigé par le prompt"),
    ("vois si tu peux faire ça", NEITHER, "01/08 — même piège idiomatique"),
    ("quelle heure il est", NEITHER, "témoin — ne rien déclencher"),
    ("explique-moi la photosynthèse", NEITHER, "témoin — culture générale"),
    ("merci, c'est parfait", NEITHER, "témoin — conversation"),
    ("combien font 17 fois 23", NEITHER, "témoin — calcul"),
]

# Seuil de couverture du test d'intégration. Les mots-clés seuls
# plafonnaient à 50 % ; en descendre serait une régression franche.
MINIMUM_COVERAGE = 0.85


def _expected_intent(label: str) -> tuple[bool, bool]:
    return label == SCREEN, label == DOCUMENTS


# ── Câblage et invariants (sans Ollama) ───────────────────────────────

@pytest.fixture(autouse=True)
def _clear_cache():
    intent._CACHE.clear()
    yield
    intent._CACHE.clear()


@pytest.fixture
def fake_classifier(monkeypatch):
    """Remplace l'appel Ollama par un dictionnaire question -> label."""

    def install(answers: dict[str, str] | None, calls: list | None = None):
        def fake(question: str):
            if calls is not None:
                calls.append(question)
            return None if answers is None else answers.get(question)

        monkeypatch.setattr(intent, "_ask_classifier", fake)

    return install


def test_labels_are_mutually_exclusive(fake_classifier):
    """
    L'invariant central. La collision RAG/vision n'est pas arbitrée après
    coup : elle est rendue impossible, parce que le classifieur ne rend
    qu'un seul label. Si ce test tombe, le bug d'origine peut revenir.
    """
    for label in (SCREEN, DOCUMENTS, NEITHER):
        fake_classifier({"q": label})
        result = classify("q")
        assert not (result.needs_screen and result.needs_documents)


def test_screen_wins_the_tie_even_in_keyword_fallback(fake_classifier):
    """
    Le repli aussi doit trancher. L'ancien code laissait les deux drapeaux
    à True sur « un document sur mon écran » — c'est précisément ce qui a
    produit le bug. Une panne d'Ollama ne doit pas le ressusciter.
    """
    fake_classifier(None)  # classifieur indisponible
    result = classify("Je voudrais une synthèse rapide d'un document sur mon écran")

    assert result.is_fallback
    assert result.needs_screen
    assert not result.needs_documents


def test_unusable_answer_falls_back(fake_classifier):
    """Une réponse hors vocabulaire est un échec, pas une devinette."""
    fake_classifier({"regarde mon écran": None})
    result = classify("regarde mon écran")

    assert result.is_fallback
    assert result.needs_screen  # les mots-clés attrapent celui-ci


def test_the_classifier_is_asked_once_per_question(fake_classifier):
    """
    Un même message traverse classify() jusqu'à quatre fois : route()
    consulte les deux axes, puis _build_messages() les reconsulte. Sans
    cache, le coût annoncé de 0,14 s serait en réalité de 0,56 s.
    """
    calls: list[str] = []
    fake_classifier({"c'est écrit quoi ?": SCREEN}, calls)

    from core.router import should_use_rag, should_use_vision

    for _ in range(3):
        should_use_vision("c'est écrit quoi ?")
        should_use_rag("c'est écrit quoi ?")

    assert len(calls) == 1


def test_a_fallback_is_never_cached(fake_classifier, monkeypatch):
    """
    Mettre un repli en cache figerait une panne passagère d'Ollama sur
    cette question pour toute la session — alors que le classifieur
    redevient peut-être disponible au message suivant.
    """
    fake_classifier(None)
    classify("une question")
    assert intent._CACHE == {}


def test_deixis_overrides_documents(fake_classifier):
    """
    Le motif « démonstratif + document » résiste aux trois modèles
    installés, et renforcer le prompt n'y change rien. La garde s'appuie
    sur la grammaire : un démonstratif désigne ce qui est présent.
    """
    for question in ("analyse ce document ouvert", "résume ce document",
                     "c'est quoi ces chiffres", "explique-moi cette page"):
        intent._CACHE.clear()
        fake_classifier({question: DOCUMENTS})
        assert classify(question).needs_screen, question


def test_relative_pronoun_is_not_deixis(fake_classifier):
    """
    « ce que » / « ce qui » sont des pronoms relatifs, pas des
    démonstratifs. Sans cette exclusion, « rappelle-moi CE QUE contient
    mon contrat » — une vraie question d'archive — basculerait vers
    l'écran et Luca's ne trouverait jamais le document.
    """
    question = "rappelle-moi ce que contient mon contrat d'assurance"
    fake_classifier({question: DOCUMENTS})

    assert classify(question).needs_documents
    assert not classify(question).needs_screen


def test_deixis_never_creates_a_document_lookup(fake_classifier):
    """
    La garde ne corrige que dans le sens DOCUMENTS → ECRAN. Elle ne doit
    jamais transformer un AUCUN en déclenchement : regarder l'écran pour
    rien coûte quelques secondes, et l'écran est du contenu sensible.
    """
    for label in (SCREEN, NEITHER):
        intent._CACHE.clear()
        fake_classifier({"donne-moi ce genre de conseil": label})
        result = classify("donne-moi ce genre de conseil")
        assert result.needs_screen == (label == SCREEN)
        assert not result.needs_documents


def test_disabled_classifier_uses_keywords(monkeypatch):
    monkeypatch.setattr(intent, "INTENT_CLASSIFIER_ENABLED", False)
    result = classify("regarde mon écran")

    assert result.is_fallback
    assert result.needs_screen


# ── Sécurité ──────────────────────────────────────────────────────────

def test_the_sensitive_guard_never_calls_the_classifier(monkeypatch):
    """
    Se tromper sur « faut-il regarder l'écran ? » coûte une réponse un peu
    moins bonne. Se tromper sur « est-ce sensible ? » envoie un relevé
    bancaire chez OpenAI. La seconde décision ne doit jamais dépendre de
    la disponibilité d'un modèle. Voir CLAUDE.md règle 3.
    """
    def boom(_question):
        raise AssertionError("is_sensitive() a consulté le classifieur")

    monkeypatch.setattr(intent, "_ask_classifier", boom)

    from core.router import is_sensitive

    assert is_sensitive("quel est mon salaire")
    assert not is_sensitive("explique-moi la photosynthèse")


def test_tts_routing_never_calls_the_classifier(monkeypatch):
    """
    route_voice() décide si du texte part chez Microsoft. Décision de
    sécurité, donc déterministe et fonctionnelle Ollama à l'arrêt — un
    classifieur indisponible ne doit jamais avoir pour effet d'AUTORISER
    une sortie.
    """
    def boom(_question):
        raise AssertionError("route_voice() a consulté le classifieur")

    monkeypatch.setattr(intent, "_ask_classifier", boom)

    from core.router import route_voice

    assert route_voice("il est de 3200 euros", "quel est mon salaire ?") == "local"
    assert route_voice("il fait beau", "quel temps fait-il ?") == "cloud"


def test_a_screen_question_stays_local(fake_classifier):
    """
    L'image ne part jamais au cloud, mais sa description en dirait autant
    (« une fenêtre affichant un solde de 3200 € »). Le basculement du
    déclencheur vers un classifieur ne doit pas avoir ouvert ce chemin.
    """
    fake_classifier({"analyse ce document ouvert": SCREEN})

    from core.router import route

    # « analyse » est un mot-clé cloud : sans la garde vision, cette
    # question partirait chez OpenAI avec le contenu de l'écran.
    assert route("analyse ce document ouvert") == "local"


# ── Couverture réelle ─────────────────────────────────────────────────

@pytest.mark.integration
def test_corpus_coverage():
    """
    Interroge le vrai modèle sur tout le corpus et affiche le score.

    C'est le seul test qui mesure la qualité du déclenchement. Les autres
    vérifient la plomberie.
    """
    failures = []
    print(f"\n{'obtenu':>10} {'attendu':>10}   question")

    for question, expected, origin in CORPUS:
        result = classify(question)
        got = (
            SCREEN if result.needs_screen
            else DOCUMENTS if result.needs_documents
            else NEITHER
        )
        ok = got == expected
        if not ok:
            failures.append((question, expected, got, origin))
        print(f"{got:>10} {expected:>10} {'   ' if ok else '<<<'} {question[:46]}")

    score = 1 - len(failures) / len(CORPUS)
    print(f"\n{len(CORPUS) - len(failures)}/{len(CORPUS)} — {score:.0%}")
    for question, expected, got, origin in failures:
        print(f"  ÉCHEC  {question}\n         attendu {expected}, obtenu {got}  ({origin})")

    assert score >= MINIMUM_COVERAGE, (
        f"couverture {score:.0%} < {MINIMUM_COVERAGE:.0%} — "
        f"{len(failures)} formulation(s) mal classée(s)"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "-s", "-m", "integration"]))
