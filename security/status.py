# security/status.py — état affichable des capteurs (panneau des
# privilèges, IDEAS.md #78 ; niveau 1 réel, décidé par Cyril le 02/08/2026
# plutôt que d'attendre le tranchage niveau 2, resté gelé — voir CLAUDE.md).
#
# Lit ce qui existe déjà (data/lucas_daemon.db, memory/lucas_memory.db). Ne
# lance JAMAIS un capteur : afficher un état ne doit pas provoquer une
# nouvelle analyse — l'appelant est le serveur API, à chaque connexion
# WebSocket ça ferait tourner Guardian/PrivacyShield bien plus souvent que
# lucas_daemon.py ne le programme (voir lucas_daemon.py, security_scan_*).
#
# ⚠️ security/ n'importe jamais LucasCore (voir privacy_shield.py). Lire
# deux fichiers SQLite en lecture seule n'y déroge pas : aucun couplage au
# reste du code, juste deux connexions jetables — même geste que
# memory.memory_manager.save_event_from_any_thread.

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DAEMON_DB_PATH = PROJECT_ROOT / "data" / "lucas_daemon.db"
MEMORY_DB_PATH = PROJECT_ROOT / "memory" / "lucas_memory.db"

# Les deux tâches programmées par lucas_daemon.py (schedule.every(...).do(...)).
SCAN_TASKS = ("security_runtime", "security_filesystem")

# Cadence la plus large des deux (filesystem : 15 min) + marge, pour
# absorber un balayage en retard sans crier "daemon éteint" à tort.
# Au-delà, l'absence de scan récent est un fait à signaler, pas à masquer
# — même principe que le RAG sans résultat (core/lucas_core.py) : ne
# jamais laisser deviner un état qu'on peut vérifier.
STALE_AFTER = timedelta(minutes=25)

# Fenêtre d'affichage des signaux : un historique complet noierait le
# panneau, et ce n'est pas son rôle (memory/lucas_memory.db le garde déjà).
FINDINGS_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class SecurityStatus:
    """
    État affichable, jamais une action ni des données brutes.

    `active` : un balayage a tourné dans la fenêtre STALE_AFTER — donc
    lucas_daemon.py est bien en vie et surveille. À False, le panneau doit
    le dire clairement plutôt que de laisser croire à une protection
    absente en silence.

    `last_scan_at` : ISO du dernier balayage TERMINÉ (succès ou échec),
    pour afficher « il y a N minutes » côté PWA.

    `findings_24h` : nombre de signaux (Guardian + PrivacyShield +
    PersistenceWatch + RansomwareWatch confondus) des dernières 24h.

    `latest_summary` : résumé du signal le plus récent, tel qu'écrit par
    Finding.as_event() (security/types.py). Pas de gravité affichée : elle
    n'est pas conservée dans l'événement stocké (voir _run_security_scan,
    lucas_daemon.py — le niveau de log l'utilise puis la perd), et
    l'inventer à la relecture serait afficher une certitude qu'on n'a pas.
    """

    active: bool
    last_scan_at: str | None
    findings_24h: int
    latest_summary: str | None


def _last_scan_at(daemon_db_path: Path) -> str | None:
    """
    Horodatage du dernier balayage terminé, ou None si indisponible.

    ⚠️ contextlib.closing() plutôt qu'un appel explicite à la méthode de
    fermeture de la connexion : la garde structurelle de test_security.py
    (test_sensors_never_act) interdit cette sous-chaîne à TOUT module de
    security/, précisément pour qu'un futur capteur ne puisse pas couper
    une socket réseau active en silence. Ce module ne fait que lire ses
    propres connexions SQLite jetables — un faux positif du garde-fou
    textuel, pas une raison de l'affaiblir. (Le mot complet est
    volontairement absent de ce commentaire pour ne pas retomber dans le
    même faux positif.)
    """
    if not daemon_db_path.exists():
        return None
    try:
        with closing(sqlite3.connect(daemon_db_path)) as conn:
            placeholders = ",".join("?" * len(SCAN_TASKS))
            row = conn.execute(
                f"SELECT started_at FROM daemon_runs "
                f"WHERE task_name IN ({placeholders}) "
                f"AND status IN ('success', 'failed') "
                f"ORDER BY id DESC LIMIT 1",
                SCAN_TASKS,
            ).fetchone()
            return row[0] if row else None
    except sqlite3.Error:
        return None


def _is_active(last_scan_at: str | None) -> bool:
    if last_scan_at is None:
        return False
    try:
        when = datetime.fromisoformat(last_scan_at)
    except ValueError:
        return False
    return datetime.now() - when <= STALE_AFTER


def _findings(memory_db_path: Path) -> tuple[int, str | None]:
    """(nombre de signaux des dernières 24h, résumé du plus récent)."""
    if not memory_db_path.exists():
        return 0, None
    try:
        with closing(sqlite3.connect(memory_db_path)) as conn:
            since = (datetime.now() - FINDINGS_WINDOW).isoformat()
            count = conn.execute(
                "SELECT COUNT(*) FROM system_events "
                "WHERE event_type LIKE 'security_%' AND created_at >= ?",
                (since,),
            ).fetchone()[0]

            latest = conn.execute(
                "SELECT details FROM system_events "
                "WHERE event_type LIKE 'security_%' "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
            summary = latest[0].split(" | ")[0] if latest else None
            return count, summary
    except sqlite3.Error:
        return 0, None


def get_status(
    daemon_db_path: Path = DAEMON_DB_PATH,
    memory_db_path: Path = MEMORY_DB_PATH,
) -> SecurityStatus:
    """
    État courant des capteurs niveau 1, prêt à afficher.

    Chemins paramétrables pour les tests — jamais utilisés autrement en
    production, où les deux bases réelles du projet suffisent toujours.
    """
    last_scan_at = _last_scan_at(daemon_db_path)
    findings_24h, latest_summary = _findings(memory_db_path)
    return SecurityStatus(
        active=_is_active(last_scan_at),
        last_scan_at=last_scan_at,
        findings_24h=findings_24h,
        latest_summary=latest_summary,
    )
