# test_derniers_mutants.py — les 29 survivants restants
#
# ⚠️ Pourquoi ce fichier existe (06/08/2026)
# ------------------------------------------
# Sixième et dernier palier de la campagne de mutation (605 mutants,
# 86 survivants). Ceux-ci sont dispersés sur 12 modules ; les regrouper
# par FAMILLE plutôt que par fichier fait ressortir ce qu'ils ont en
# commun — et évite d'écrire douze fois le même test.
#
#   • blocs de démonstration : importer un module ne doit rien exécuter
#   • replis `X or DÉFAUT`   : une valeur absente prend le défaut
#   • dataclasses gelées     : ce qui décrit une décision ne se réécrit pas
#   • et une poignée de cas isolés, chacun documenté sur place

from __future__ import annotations

import importlib
import inspect
import sys

import pytest

# ══ Blocs de démonstration — l'import ne doit rien exécuter ══════════

@pytest.mark.parametrize(
    "module",
    [
        "modules.web_search",
        "modules.calculator",
        "modules.vision_manager",
        "modules.voice_manager",
    ],
)
def test_importing_a_module_runs_no_demo(module: str, capsys) -> None:
    """
    Mutant : `if __name__ == "__main__"` -> `!=`. Inversé, le simple
    IMPORT exécute la démo du module — une vraie recherche web pour
    `web_search`, une vraie synthèse vocale pour `voice_manager`, une
    capture d'écran pour `vision_manager`.

    Un effet de bord au chargement d'un module se découvre très loin de
    sa cause : il se déclenche à l'import d'autre chose.

    ⚠️ C'est la SORTIE STANDARD qu'on observe, pas un double de classe :
    `reload()` réexécute le module et redéfinit ses classes avant
    d'atteindre le bloc, donc toute sentinelle serait écrasée (piège
    rencontré sur `rag_manager`).
    """
    # ⚠️ Importer AVANT de recharger : `sys.modules` ne contient que ce
    # qui a deja ete importe, et ces modules ne le sont pas forcement
    # au moment ou ce test tourne.
    importlib.import_module(module)
    capsys.readouterr()
    importlib.reload(sys.modules[module])
    assert capsys.readouterr().out.strip() == "", (
        f"l'import de {module} ne doit rien afficher — la démo s'est exécutée"
    )


# ══ Replis `X or DÉFAUT` — l'absence prend la valeur par défaut ══════

def test_an_omitted_stt_model_size_falls_back_to_the_configured_one() -> None:
    """
    Mutant stt_engine:83 : `model_size or STT_MODEL_SIZE` -> `and`. Avec
    `and`, omettre le paramètre donne `None` comme taille de modèle — et
    Whisper échoue au chargement, bien après.
    """
    from config import STT_MODEL_SIZE
    from modules.stt_engine import STTEngine

    assert STTEngine().model_size == STT_MODEL_SIZE
    assert STTEngine(model_size="tiny").model_size == "tiny", (
        "une valeur fournie doit primer sur le défaut"
    )


def test_an_omitted_voice_falls_back_to_the_configured_one() -> None:
    """Mutant voice_manager:43 : même motif, sur la voix edge_tts."""
    from config import EDGE_TTS_VOICE
    from modules.voice_manager import VoiceManager

    assert VoiceManager().voice == EDGE_TTS_VOICE
    assert VoiceManager(voice="fr-FR-DeniseNeural").voice == "fr-FR-DeniseNeural"


# ══ Dataclasses gelées — une décision ne se réécrit pas ══════════════

def test_an_aura_mode_change_cannot_be_rewritten() -> None:
    """
    Mutant aura_modes:206 : `@dataclass(frozen=True)` -> `False`.

    `AuraModeChange` décrit un changement de mode DEMANDÉ par Cyril. Le
    réécrire après coup ferait diverger ce que Luca's fait de ce qu'il a
    demandé.
    """
    import dataclasses

    from core.aura_modes import AuraMode, AuraModeChange

    changement = AuraModeChange(AuraMode.DEEP_FOCUS, "commande explicite")
    with pytest.raises(dataclasses.FrozenInstanceError):
        changement.mode = AuraMode.SOCIAL  # type: ignore[misc]  # l'interdit testé


def test_an_action_spec_cannot_be_rewritten() -> None:
    """
    ⚠️ Mutant decision_engine:63 : `@dataclass(frozen=True)` -> `False`.

    `ActionSpec` porte la CATÉGORIE d'une action — lecture, écriture,
    exécution — celle qui décide si une confirmation est requise. Modifier
    cette catégorie après enregistrement contournerait la décision
    elle-même.
    """
    import dataclasses

    from core.decision_engine import ActionCategory, ActionSpec

    spec = ActionSpec("launch_notepad", ActionCategory.EXECUTE)
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.category = ActionCategory.READ  # type: ignore[misc]  # l'interdit testé


# ══ api/protocol.py:226 / 241 — une valeur non-texte est refusée ═════

@pytest.mark.parametrize("lecteur", ["read_user_audio", "read_user_image"])
@pytest.mark.parametrize("charge", [123, ["QUJD"], {"b64": "QUJD"}, None])
def test_a_non_text_payload_is_refused(lecteur: str, charge) -> None:
    """
    Mutants 226 et 241 : `isinstance(value, str) and value.strip()` ->
    `or`. Avec `or`, un entier ou une liste passe le test, et `.strip()`
    est appelé dessus — le handler WebSocket tombe sur un AttributeError
    au lieu de refuser proprement une trame malformée.
    """
    from api import protocol

    champ = "audio_base64" if "audio" in lecteur else "image_base64"
    assert getattr(protocol, lecteur)({champ: charge}) == ""


# ══ core/dates.py:179 — une année couvre ses mois ════════════════════

def test_a_year_covers_its_months() -> None:
    """
    Mutant : `if "-" not in period` -> `in`. La règle : demander « 2025 »
    doit retrouver un document daté « 2025-07 ». Inversée, une demande
    d'ANNÉE ne couvre plus rien, et une demande de MOIS se met à couvrir
    des choses qu'elle ne devrait pas.
    """
    from core.dates import matches

    # ⚠️ La fonction s'appelle `matches`, et son second paramètre est la
    # CHAÎNE stockée en métadonnée (périodes séparées par des virgules),
    # pas un ensemble. Vérifié plutôt que supposé.
    assert matches("2025", "2025-07") is True, "une année couvre ses mois"
    assert matches("2025", "2024-07") is False


# ══ core/router.py:328 — pas d'opérateur, pas de calcul ══════════════

def test_a_string_without_an_operator_is_not_an_expression() -> None:
    """
    Mutant : `if not any(op in best for op in "+-*/%")` -> `not in`.
    Inversé, une suite de nombres sans opérateur devient une « expression »
    — et Luca's annonce un calcul qu'elle n'a pas fait.
    """
    from core.router import extract_calculation

    assert extract_calculation("les codes 12 34 56 et 78") is None
    assert extract_calculation("combien font 12 + 34 ?") is not None


# ══ modules/semantic_desktop.py:54 — le garde du mode dégradé ════════

def test_semantic_search_degrades_when_the_collection_is_missing() -> None:
    """
    Mutant : `not (self.rag.use_chroma and self.rag.collection)` -> `or`.

    Même famille que les quatre gardes de `rag_manager` : l'état MIXTE
    (`use_chroma` vrai, collection absente) est le seul qui distingue les
    deux écritures. Avec `or`, le garde se déclenche même quand tout va
    bien — la recherche sémantique rendrait toujours une liste vide.
    """
    from modules.semantic_desktop import SemanticDesktop

    class _RagMixte:
        use_chroma = True
        collection = None

    class _RagComplet:
        use_chroma = True

        class collection:
            @staticmethod
            def get(**kw):
                # Aucun morceau pour ce document : `related_documents` sort
                # sur une liste vide, mais APRÈS le garde — c'est ce qui
                # distingue les deux écritures.
                return {"documents": [], "metadatas": [], "ids": []}

            @staticmethod
            def query(**kw):
                return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    bureau = SemanticDesktop.__new__(SemanticDesktop)
    bureau.rag = _RagMixte()  # type: ignore[assignment]  # double assumé
    assert bureau.related_documents("note.txt") == []

    bureau.rag = _RagComplet()  # type: ignore[assignment]  # double assumé
    assert bureau.related_documents("note.txt") == [], (
        "collection présente : le garde ne doit PAS court-circuiter"
    )


# ══ modules/finance_manager.py — dépenses et lignes vides ════════════

def test_expenses_are_the_negative_amounts() -> None:
    """
    Mutants 286 et 295 : `t["montant"] < 0` -> `>=`. Inversés, les
    REVENUS deviennent les dépenses — le total mensuel affiché à Cyril
    serait faux dans les grandes largeurs, sans qu'aucune erreur ne
    s'affiche.
    """
    from modules.finance_manager import FinanceManager

    manager = FinanceManager()
    manager.transactions = [
        {"date": None, "libelle": "SALAIRE", "montant": 2400.0, "categorie": "Revenus"},
        {"date": None, "libelle": "COURSES", "montant": -84.3, "categorie": "Alimentation"},
        {"date": None, "libelle": "ESSENCE", "montant": -60.0, "categorie": "Transport"},
    ]

    assert manager.get_expense_total() == pytest.approx(144.3), (
        "seuls les montants négatifs sont des dépenses"
    )
    par_categorie = manager.get_expenses_by_category()
    assert "Revenus" not in par_categorie, "un revenu n'est pas une dépense"
    assert par_categorie["Alimentation"] == pytest.approx(84.3)


def test_a_row_with_a_date_but_no_label_is_still_a_transaction() -> None:
    """
    Mutant 248 : `if not raw_date and not label` -> `or`. Avec `or`, une
    ligne à laquelle il manque l'UN des deux champs est jetée — alors que
    la règle est de ne jeter que les lignes VIDES (fin de fichier).
    Un relevé sans libellé sur une ligne perdrait la transaction.
    """
    from modules.finance_manager import FinanceManager

    manager = FinanceManager()
    colonnes = {"date": "date", "libelle": "libelle", "montant": "montant"}
    ligne = {"date": "05/01/2026", "libelle": "", "montant": "-42,00"}

    assert manager._parse_row(ligne, colonnes, use_llm=False, ask=None) is not None, (
        "seule une ligne entièrement vide doit être écartée"
    )


def test_importing_a_csv_uses_the_llm_by_default() -> None:
    """
    Mutant 134 : `use_llm: bool = True` -> `False`. `import_csv` est le
    chemin d'import MANUEL, où l'on accepte de payer la catégorisation
    LLM une fois pour toutes — contrairement à `load_directory`, appelé à
    chaque question et volontairement à `False` (voir sa docstring).
    Basculer ce défaut viderait l'import manuel de sa raison d'être.
    """
    from modules.finance_manager import FinanceManager, load_directory

    assert inspect.signature(FinanceManager.import_csv).parameters["use_llm"].default is True
    assert inspect.signature(load_directory).parameters["use_llm"].default is False, (
        "les deux défauts sont opposés À DESSEIN"
    )


# == modules/voice_manager.py:82 - l'extrait tronque le dit ==========

def test_a_truncated_log_excerpt_is_marked_as_such() -> None:
    """
    Mutant : `if len(text) > LOG_EXCERPT_LENGTH` -> `<=`. Les extraits en
    base sont tronques a 80 caracteres pour que la table d'evenements ne
    devienne pas une copie du contenu qu'on refuse d'envoyer (CLAUDE.md,
    routage TTS). Le marqueur « ... » dit que le texte continue — inverse,
    il apparait sur les textes courts et disparait sur les longs.

    ⚠️ La troncature est EN LIGNE dans `_log`, pas dans une methode
    isolable : on observe donc ce qui est reellement journalise.
    """
    # ⚠️ `event_recorder()` plutôt qu'une lambda : mypy ne sait pas
    # vérifier une lambda contre un type UNION (`Callable | None`), et rend
    # « Cannot infer type of lambda » — même motif que les 14 lambdas
    # remplacées ce matin (ROADMAP.md §5.61).
    from conftest import event_recorder
    from modules.voice_manager import LOG_EXCERPT_LENGTH, VoiceManager

    evenements, log_event = event_recorder()
    manager = VoiceManager(log_event=log_event)

    manager._log("test_court", "phrase courte")
    manager._log("test_long", "x" * (LOG_EXCERPT_LENGTH + 50))

    court = next(d for t, d in evenements if t == "test_court")
    long = next(d for t, d in evenements if t == "test_long")

    assert "\u2026" not in court, "un texte court n'est pas tronque"
    assert "\u2026" in long, "un texte tronque doit le signaler"


# ══ modules/stt_engine.py — le chemin audio du pont mobile ═══════════

def test_a_malformed_base64_audio_is_refused() -> None:
    """
    Mutant 169 : `validate=True` -> `False`. Sans validation, les
    caractères invalides sont IGNORÉS et des octets tronqués sont écrits
    dans un fichier temporaire, puis passés à Whisper — qui échoue bien
    plus loin, sur un symptôme sans rapport.
    """
    from modules.stt_engine import STTEngine, STTUnavailable

    with pytest.raises((STTUnavailable, Exception)):
        STTEngine().transcribe_base64("QUJD!")


def test_the_transcription_cache_evicts_the_oldest_entry() -> None:
    """
    Mutant 198 : `self._cache.popitem(last=False)` -> `True`. `last=False`
    retire le PLUS ANCIEN (FIFO) ; à True, c'est le plus récent qui part —
    et le cache expulse systématiquement ce qu'on vient d'y mettre, donc
    ne sert plus à rien tout en donnant l'illusion d'exister.
    """
    from config import STT_CACHE_SIZE
    from modules.stt_engine import STTEngine, TranscriptResult

    def _resultat(texte: str) -> TranscriptResult:
        """⚠️ `_remember` attend un TranscriptResult, pas une chaîne —
        mypy l'a rattrapé. Remplir une structure avec le mauvais type
        testerait une forme qui n'existe pas en production."""
        return TranscriptResult(text=texte, language="fr", confidence=0.9, duration_seconds=1.0)

    moteur = STTEngine()
    for i in range(STT_CACHE_SIZE + 2):
        moteur._remember(f"cle{i}", _resultat(f"valeur{i}"))

    assert "cle0" not in moteur._cache, "le plus ancien doit être expulsé"
    dernier = f"cle{STT_CACHE_SIZE + 1}"
    assert dernier in moteur._cache, (
        "le plus RÉCENT doit rester : sinon le cache expulse ce qu'on vient d'y mettre"
    )


# ══ core/ollama_client.py:36 — le streaming n'est jamais le défaut ═══

def test_ollama_requests_are_not_streamed_by_default() -> None:
    """
    Mutant : `stream: bool = False` -> `True`. Tous les appelants qui ne
    précisent rien — le classifieur d'intention, `local_llm` — lisent la
    réponse d'un bloc avec `.json()`. En streaming, ils reçoivent une
    suite de fragments et le parsing échoue.

    Seul `llm_worker` demande explicitement `stream=True` (mutants 32/34),
    parce que lui affiche la réponse au fil de l'eau.
    """
    from core.ollama_client import post_chat

    assert inspect.signature(post_chat).parameters["stream"].default is False


def test_the_ui_worker_asks_for_streaming_explicitly() -> None:
    """
    Mutants llm_worker:32 et 34 : `"stream": True` et `stream=True` ->
    `False`. Sans streaming, la réponse arrive d'un bloc à la fin —
    l'affichage progressif de l'interface disparaît, et Cyril attend
    devant un écran figé.
    """
    import inspect as _inspect

    from core import llm_worker

    source = _inspect.getsource(llm_worker.LLMWorker.run)
    assert '"stream": True' in source, "le flux doit être demandé dans la charge utile"
    assert "stream=True" in source, "et au transport HTTP"


# ══ modules/piper_engine.py:78 — le dossier de sortie est créé ═══════

def test_piper_creates_the_output_directory(monkeypatch, tmp_path) -> None:
    """
    Mutant : `mkdir(parents=True, exist_ok=True)` -> `parents=False`. Au
    premier usage, `data/voices/` n'existe pas encore : sans `parents`,
    la synthèse échoue sur un `FileNotFoundError` que rien ne rattrape.
    """
    from modules.piper_engine import PiperEngine

    moteur = PiperEngine()
    if not moteur.is_available():
        pytest.skip("modèle Piper absent sur cette machine")

    cible = tmp_path / "un" / "deux" / "sortie.wav"
    assert not cible.parent.exists()
    moteur.synthesize("test", str(cible))
    assert cible.exists()


# ══ modules/web_search.py:173 / 175 / 196 — les replis d'affichage ═══

def test_a_cancelled_search_without_a_body_still_explains_itself(monkeypatch) -> None:
    """
    Mutant 173 : `results[0].get("body") or REFUSAL_MESSAGE` -> `and`.

    Quand la recherche est ANNULÉE — le filtre anti-fuite a détecté une
    donnée identifiante dans la requête —, le message de refus doit
    arriver à Cyril. Avec `and`, un faux résultat sans `body` rend une
    chaîne VIDE : la recherche est refusée en silence, et Cyril croit
    à une panne.
    """
    from modules import web_search as ws

    moteur = ws.WebSearch()
    monkeypatch.setattr(moteur, "search", lambda q, n=3: [{"title": "recherche annulée"}])

    texte, issue = moteur.get_summary_with_outcome("mon iban")
    assert issue == "refused"
    assert texte == ws.REFUSAL_MESSAGE, "un refus sans corps doit expliquer pourquoi"


def test_a_failed_search_without_a_body_still_says_it_failed(monkeypatch) -> None:
    """Mutant 175 : même motif, sur le faux résultat « erreur »."""
    from modules import web_search as ws

    moteur = ws.WebSearch()
    monkeypatch.setattr(moteur, "search", lambda q, n=3: [{"title": "erreur"}])

    texte, issue = moteur.get_summary_with_outcome("météo")
    assert issue == "failed"
    assert texte.strip(), "un échec sans corps doit quand même dire quelque chose"


def test_a_result_without_a_url_is_still_displayed(monkeypatch) -> None:
    """
    Mutant 196 : `result.get("href") or ""` -> `and`. Avec `and`, un
    résultat QUI A une URL la perd (l'expression rend `""`), et le lien
    disparaît du résumé — Cyril ne peut plus vérifier la source.
    """
    from modules import web_search as ws

    moteur = ws.WebSearch()
    monkeypatch.setattr(
        moteur, "search",
        lambda q, n=3: [{"title": "Un titre", "href": "https://exemple.fr", "body": "Un corps"}],
    )

    resume = moteur.get_summary("quoi que ce soit")
    assert "https://exemple.fr" in resume, "l'URL doit rester affichée"


# ══ modules/stt_engine.py:169 / 175 / 181 — le fichier temporaire ════

def test_a_malformed_base64_audio_is_named_as_such() -> None:
    """
    Mutant 169 : `validate=True` -> `False`.

    ⚠️ Ma première version se contentait d'attendre « une exception » —
    et les deux versions en lèvent une, pour des raisons différentes.
    Ce qui distingue, c'est LAQUELLE : sans validation, les caractères
    invalides sont ignorés, des octets tronqués partent dans un fichier
    temporaire, et l'échec survient bien plus loin, chez Whisper.
    """
    from modules.stt_engine import STTEngine, STTUnavailable

    with pytest.raises(STTUnavailable) as leve:
        STTEngine().transcribe_base64("QUJD!")

    assert "base64" in str(leve.value).lower(), (
        "l'échec doit être attribué au décodage, pas à la transcription"
    )


def test_the_temp_audio_file_survives_until_transcription(monkeypatch) -> None:
    """
    Mutant 175 : `NamedTemporaryFile(..., delete=False)` -> `True`. Avec
    `delete=True`, le fichier est supprimé à la fermeture du `with` —
    donc AVANT que `transcribe()` ne le lise. Whisper reçoit un chemin
    qui n'existe plus.
    """
    import os

    from modules.stt_engine import STTEngine

    vus: list[bool] = []
    moteur = STTEngine()

    # Fonction nommée plutôt que `vus.append(...) or None` : l'idiome
    # marche, mais s'appuie sur la valeur de retour d'une méthode qui n'en
    # a pas — même motif corrigé ce matin dans finance_manager.py.
    def _note_si_le_fichier_existe(chemin):
        vus.append(os.path.exists(chemin))

    monkeypatch.setattr(moteur, "transcribe", _note_si_le_fichier_existe)

    moteur.transcribe_base64("QUJD")
    assert vus == [True], "le fichier doit exister quand la transcription le lit"


def test_a_temp_audio_file_already_gone_does_not_break_the_cleanup(monkeypatch) -> None:
    """
    Mutant 181 : `unlink(missing_ok=True)` -> `False`. Le nettoyage est
    dans un `finally` : si le fichier a déjà disparu — antivirus, purge
    du dossier temp —, il lèverait par-dessus le RÉSULTAT de la
    transcription, qui serait perdu.
    """
    import os

    from modules.stt_engine import STTEngine

    moteur = STTEngine()

    def _transcrit_puis_supprime(chemin):
        os.unlink(chemin)  # le fichier disparaît avant le finally
        return "audio transcrit"

    monkeypatch.setattr(moteur, "transcribe", _transcrit_puis_supprime)

    assert moteur.transcribe_base64("QUJD") == "audio transcrit", (
        "le nettoyage ne doit jamais emporter le résultat"
    )
