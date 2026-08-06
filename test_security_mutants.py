# test_security_mutants.py — les trous révélés par la campagne de mutation
#
# ⚠️ Pourquoi ce fichier existe (06/08/2026)
# ------------------------------------------
# Le projet était à 100 % de COUVERTURE. Une campagne de mutation (605
# mutants, 52 min) a mesuré autre chose : 86 mutants ont SURVÉCU — du code
# qu'on peut casser sans qu'aucun test ne s'en aperçoive. Score 85,5 %.
#
# La couverture dit « cette ligne s'exécute ». La mutation dit « si cette
# ligne faisait le contraire, quelqu'un le remarquerait ». Les deux ne
# mesurent pas la même chose, et l'écart est précisément ce qui reste à
# combler.
#
# Ce fichier traite les 11 survivants de `security/` — traités en premier
# parce que c'est le module où CLAUDE.md place le plus d'exigence, et
# parce qu'un capteur qui se trompe en silence est pire que pas de capteur.

from __future__ import annotations

import json
import time

import pytest

# ══ security/status.py:43 — l'état affichable est IMMUABLE ════════════

def test_the_security_status_cannot_be_mutated_after_the_fact() -> None:
    """
    `@dataclass(frozen=True)` est une garantie de conception : l'état est
    « affichable, jamais une action ni des données brutes ». Sans gel, un
    appelant pourrait le réécrire en mémoire — un panneau de sécurité qui
    ment devient pire qu'un panneau absent.

    Le mutant `frozen=True -> False` survivait : rien ne le vérifiait.
    """
    import dataclasses

    from security.status import SecurityStatus

    etat = SecurityStatus(
        active=True, last_scan_at="2026-08-06 10:00:00",
        findings_24h=0, latest_summary=None,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        etat.active = False  # type: ignore[misc]  # c'est précisément l'interdit testé


# ══ security/history.py — la mémoire des comportements ════════════════

def test_a_corrupted_history_entry_is_dropped_not_loaded(tmp_path) -> None:
    """
    L'historique vient d'un fichier JSON sur disque, qui peut être tronqué
    ou modifié. Une entrée malformée chargée telle quelle ferait planter
    un capteur PLUS TARD, loin de la cause.

    Mutant survivant : `isinstance(value, dict) and "first_seen" in value`
    -> `or`. Avec `or`, une chaîne ou un dict incomplet passait.
    """
    import time

    from security.history import BehaviourHistory

    maintenant = time.time()
    chemin = tmp_path / "historique.json"
    # ⚠️ `first_seen` est un timestamp FLOAT (time.time()), pas une chaîne
    # ISO — et `_purge()` tourne juste après le chargement. Une date mal
    # formée serait écartée pour la mauvaise raison, et le test ne
    # prouverait rien du filtre qu'il vise.
    chemin.write_text(json.dumps({
        "started_at": maintenant,
        "entries": {
            "correct": {"first_seen": maintenant, "last_seen": maintenant},
            "pas_un_dict": "chaine",
            # ⚠️ `last_seen` RÉCENT mais pas de `first_seen` : sans ça,
            # `_purge()` écarterait l'entrée pour une tout autre raison
            # (trop vieille), et le test passerait sans rien prouver du
            # filtre qu'il vise. Première version de ce test : exactement
            # ce piège.
            "dict_incomplet": {"last_seen": maintenant},
        },
    }), encoding="utf-8")

    histoire = BehaviourHistory(chemin)

    assert histoire.has_seen("correct")
    assert not histoire.has_seen("pas_un_dict"), "une entrée non-dict doit être écartée"
    assert not histoire.has_seen("dict_incomplet"), "sans first_seen, l'entrée est inutilisable"


def test_saving_history_creates_the_missing_directories(tmp_path) -> None:
    """
    Premier lancement sur une machine neuve : `data/security/` n'existe
    pas encore. `mkdir(parents=True)` doit créer TOUTE la chaîne.

    Mutant survivant : `parents=True` -> `False`. Le `FileNotFoundError`
    qui s'ensuit est un `OSError`, donc avalé par le `except OSError` de
    `save()` — l'historique n'était JAMAIS écrit au premier démarrage, en
    silence, et chaque lancement re-signalait tout comme neuf.

    ⚠️ Ma première version créait le dossier avant d'enregistrer. Elle
    testait donc `exist_ok`, pas `parents` — et laissait le mutant
    survivre. Le chemin doit être IMBRIQUÉ et ABSENT.
    """
    from security.history import BehaviourHistory

    chemin = tmp_path / "data" / "security" / "historique.json"
    assert not chemin.parent.exists(), "le test exige des dossiers absents au départ"

    histoire = BehaviourHistory(chemin)
    histoire.remember("chrome.exe")
    histoire.save()

    assert chemin.exists(), "l'historique doit être écrit, dossiers créés au passage"
    relu = BehaviourHistory(chemin)
    assert relu.has_seen("chrome.exe"), "ce qui est enregistré doit être relisible"


# ══ security/monitor.py — construction et état ════════════════════════

def test_a_monitor_built_without_history_gets_a_real_one(tmp_path) -> None:
    """
    Mutant survivant : `history if history is not None else ...` -> `is`.
    Inversé, un moniteur construit AVEC un historique le jetterait, et
    l'historique fourni par l'appelant serait ignoré sans un mot.
    """
    from security.history import BehaviourHistory
    from security.monitor import SecurityMonitor

    fourni = BehaviourHistory(tmp_path / "h.json")
    assert SecurityMonitor(history=fourni).history is fourni, (
        "l'historique fourni doit être celui utilisé"
    )
    assert SecurityMonitor().history is not None, (
        "sans historique fourni, le moniteur doit en construire un"
    )


def test_saving_monitor_state_creates_the_missing_directories(tmp_path) -> None:
    """Même piège que pour l'historique, et même correction."""
    from security.monitor import SecurityMonitor

    etat = tmp_path / "data" / "security" / "etat.json"
    assert not etat.parent.exists(), "le test exige des dossiers absents au départ"

    moniteur = SecurityMonitor(state_path=etat)
    # `_seen` associe un signal a un TIMESTAMP (float), pas a une chaine
    # ISO — mypy l'a rattrape. Un test qui remplit la structure avec le
    # mauvais type teste une forme qui n'existe pas en production.
    moniteur._seen["signal_test"] = time.time()
    moniteur._save_state()

    assert etat.exists(), "l'état doit être écrit, dossiers créés au passage"
    assert "signal_test" in json.loads(etat.read_text(encoding="utf-8"))


# ══ security/persistence_watch.py — l'historique est bien enregistré ══

def test_the_watcher_persists_its_history_after_a_scan(tmp_path) -> None:
    """
    Mutant survivant : `if self.history is not None:` -> `is`. Inversé,
    l'historique n'était JAMAIS enregistré — et chaque balayage
    re-signalait les mêmes entrées comme nouvelles, indéfiniment.
    """
    from security.history import BehaviourHistory
    from security.persistence_watch import PersistenceWatch

    chemin = tmp_path / "h.json"
    histoire = BehaviourHistory(chemin)
    veille = PersistenceWatch(history=histoire)
    veille.scan()

    assert chemin.exists(), "un balayage doit enregistrer l'historique sur disque"


# ══ Les preuves affichées à Cyril ═════════════════════════════════════

def test_an_unknown_executable_path_is_named_not_left_blank() -> None:
    """
    Les signaux portent une `evidence` que Cyril lit dans le panneau.
    Quand le chemin de l'exécutable est inaccessible (fréquent sur les
    process système), le repli doit dire « inconnu » — un champ vide
    ressemble à un bug d'affichage, pas à une information.

    Mutant survivant : `exe or "inconnu"` -> `and`. Avec `and`, le champ
    devenait vide (ou pire, le chemin disparaissait quand il existait).
    """
    from security.guardian import Guardian
    from security.privacy_shield import PrivacyShield

    signal = Guardian._check_lookalike_name("svch0st.exe", "")
    assert signal is not None
    assert signal.evidence["chemin"] == "inconnu"

    class _Adresse:
        ip = "0.0.0.0"
        port = 4444

    # 3e parametre = le CHEMIN de l'executable, pas un PID.
    ecoute = PrivacyShield._check_wide_open_listener("x.exe", _Adresse(), "")
    assert ecoute is not None
    assert ecoute.evidence["chemin"] == "inconnu"


def test_a_known_executable_path_is_reported_as_is() -> None:
    """Contrôle inverse : quand le chemin existe, c'est LUI qui s'affiche."""
    from security.guardian import Guardian

    signal = Guardian._check_lookalike_name("svch0st.exe", r"C:\Temp\svch0st.exe")
    assert signal is not None
    assert signal.evidence["chemin"] == r"C:\Temp\svch0st.exe"


# ══ Les trois survivants du SECOND passage ═══════════════════════════
#
# ⚠️ Pourquoi ils sont arrivés après coup.
#
# Sur les 11 survivants de `security/` traités en premier, ma
# vérification n'en a rejoué que HUIT. `privacy_shield:154` et `:189`
# n'ont jamais été vérifiés — je les avais comptés comme traités sans
# preuve. C'est exactement l'erreur traquée ailleurs : rapporter un
# succès sans l'avoir constaté.
#
# Le troisième, dans `ransomware_watch`, appartient à une catégorie
# entière — les négations — que mon outil de mutation écartait en
# silence : le garde de frontière de mot examinait le caractère suivant
# l'espace de `"not "`, donc échouait toujours.

def test_a_first_contact_without_a_path_is_still_named() -> None:
    """
    Mutant privacy_shield:154 : `exe or "inconnu"` -> `and`.

    Même motif que celui déjà couvert pour l'écoute grande ouverte, mais
    sur l'AUTRE capteur — le premier contact avec une adresse publique.
    Deux fonctions, deux `evidence`, deux tests : n'en couvrir qu'une
    laissait l'autre mutant vivant.
    """
    from security.privacy_shield import PrivacyShield

    # ⚠️ Sans historique injecté, ce contrôle NE S'APPLIQUE PAS (l.141) :
    # il rend None avant d'atteindre la ligne visée. Ma première version
    # construisait un PrivacyShield nu et testait donc le mauvais chemin.
    class _HistoireNeuve:
        def is_new(self, cle):
            return True

    shield = PrivacyShield(history=_HistoireNeuve())
    signal = shield._check_first_external_contact("x.exe", "", "93.184.216.34")
    assert signal is not None
    assert signal.evidence["chemin"] == "inconnu"

    connu = shield._check_first_external_contact(
        "y.exe", r"C:\Program Files\y.exe", "93.184.216.35"
    )
    assert connu is not None
    assert connu.evidence["chemin"] == r"C:\Program Files\y.exe"


def test_a_listening_socket_without_an_address_is_skipped(monkeypatch) -> None:
    """
    Mutant privacy_shield:189 : `conn.status == CONN_LISTEN and conn.laddr`
    -> `or`.

    Une socket en écoute SANS adresse locale existe — psutil rend parfois
    `laddr` vide sur des connexions transitoires. Avec `or`, le capteur
    appelle `_check_wide_open_listener` avec `laddr` vide et tombe sur un
    AttributeError : le balayage entier s'arrête, et plus aucun signal
    n'est produit.
    """
    import psutil

    from security.privacy_shield import PrivacyShield

    class _Connexion:
        pid = 4242
        status = psutil.CONN_LISTEN
        laddr = ()          # écoute, mais sans adresse
        raddr = None

    shield = PrivacyShield()
    monkeypatch.setattr(psutil, "net_connections", lambda kind="inet": [_Connexion()])
    monkeypatch.setattr(
        shield, "_describe_process", lambda pid: ("app.exe", r"C:\app.exe")
    )

    assert shield.scan() == [], "une socket sans adresse ne produit aucun signal"


def test_a_shell_folder_that_is_a_real_directory_is_kept(monkeypatch, tmp_path) -> None:
    """
    Mutant ransomware_watch:104 : `if resolved is None or not resolved.is_dir()`
    -> le `not` disparaît.

    Inversé, un dossier RÉSOLU et existant — typiquement « Documents »
    redirigé vers OneDrive — est jeté au profit de `~/Documents`, qui
    n'existe pas sur une machine où la redirection est active. La veille
    ransomware surveillerait alors un dossier vide, en silence.
    """
    from security import ransomware_watch as rw

    reel = tmp_path / "OneDrive" / "Documents"
    reel.mkdir(parents=True)

    monkeypatch.setattr(
        rw, "_resolve_shell_folder",
        lambda nom: reel if nom == rw.RANSOMWARE_WATCH_DIRS[0] else None,
    )

    dossiers = rw._watched_directories()
    assert reel in dossiers, (
        "un dossier résolu et existant doit être surveillé, pas remplacé "
        "par un chemin par défaut qui n'existe peut-être pas"
    )
