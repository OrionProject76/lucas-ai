"""
Lucas Daemon — Cerveau nocturne de Luca's AI
Tourne 24/7 en arrière-plan sur le PC maître.
Gère : entraînement LoRA, indexation RAG, screenshots, cleanup, logs émotionnels.

Lancement :
    pythonw lucas_daemon.py          (Windows, sans fenêtre)
    ou : nssm install LucasDaemon ... (service Windows)

Auteur : Lucas AI Project

── Convention d'horodatage de ce fichier ─────────────────────────────

Tout ce que ce daemon écrit — journal, `daemon_runs.started_at`,
`emotional_logs.timestamp`, noms de captures — utilise l'heure LOCALE
naïve (`datetime.now()`), et c'est délibéré : ces valeurs sont lues par
Cyril. Un journal en UTC afficherait « 01:05 » pour un événement de
3h05 du matin.

⚠️ Ce qui est interdit, en revanche, c'est de COMPARER ces valeurs à
celles écrites par SQLite (`CURRENT_TIMESTAMP`, qui est en UTC). C'est
ce mélange — pas l'heure locale elle-même — qui a produit le bug du
06/08/2026 dans `security/status.py`, où le panneau affichait « aucun
signal » alors qu'il y en avait (ROADMAP.md §5.59).

`security/status.py::_is_active` lit bien `started_at` d'ici en heure
locale, et c'est correct. Toute nouvelle lecture croisée doit vérifier
laquelle des deux conventions s'applique.
"""

# La convention ci-dessus vaut pour tout le fichier : la déclarer une
# fois évite d'ajouter le même `noqa` à quinze endroits.
# ruff: noqa: DTZ005, DTZ006

import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import schedule

# ─── CONFIGURATION ─────────────────────────────────────────
LUCAS_ROOT = Path("C:/OrionAI")
DATA_DIR = LUCAS_ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
MODELS_DIR = LUCAS_ROOT / "models"
TRAINING_DIR = LUCAS_ROOT / "training"
REPORTS_DIR = DATA_DIR / "reports"

# Créer les dossiers manquants
for d in [DATA_DIR, LOGS_DIR, SCREENSHOTS_DIR, MODELS_DIR, TRAINING_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOGS_DIR / "daemon.log"
DB_FILE = DATA_DIR / "lucas_daemon.db"
# CONFIG_FILE (config.json) retiré le 06/08/2026 : la constante était
# définie ici et consommée nulle part — aucun `json.load` dans ce
# fichier, et la clé qu'il contient (`profiles.enabled`) n'apparaît dans
# aucun module du projet. Elle donnait l'impression que le daemon lisait
# une configuration utilisateur, ce qui n'a jamais été le cas.
# Voir ROADMAP.md §5.58.

# ─── LOGGING ───────────────────────────────────────────────
def log(msg: str, level: str = "INFO"):
    """Log avec timestamp dans fichier et console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ─── BASE DE DONNÉES ───────────────────────────────────────
def init_db():
    """Initialise la base SQLite du daemon."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS daemon_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            duration_seconds REAL,
            details TEXT,
            error TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS emotional_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            emotion TEXT,
            confidence REAL,
            source TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS screenshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            filepath TEXT,
            app_active TEXT,
            hash TEXT
        )
    """)
    conn.commit()
    conn.close()
    log("Base de données initialisée.")

def db_log_task(task_name: str, status: str, details: str = "", error: str = ""):
    """Log une tâche dans la base."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("""
        INSERT INTO daemon_runs (task_name, status, started_at, details, error)
        VALUES (?, ?, ?, ?, ?)
    """, (task_name, status, now, details, error))
    conn.commit()
    conn.close()

# ─── TÂCHES NOCTURNES ──────────────────────────────────────

class LucasDaemon:
    """Daemon principal de Luca's AI.

    ── Pourquoi ces `except Exception` ───────────────────────────────

    Chaque tâche planifiée en attrape un, et c'est délibéré : ce
    processus tourne 24/7 sans surveillance. Une tâche qui plante ne
    doit pas emporter le daemon avec elle — sinon une erreur ponctuelle
    dans l'indexation RAG couperait aussi les balayages de sécurité et
    le rapport du matin, en silence, jusqu'au prochain redémarrage
    manuel.

    ⚠️ La condition qui rend ces `except` acceptables : **ils
    journalisent tous**. Un `except Exception: pass` muet dans ce
    fichier serait le contraire — deux existaient, corrigés le
    06/08/2026 (ROADMAP.md §5.59). C'est cette différence, pas le type
    d'exception attrapé, qui sépare une dégradation maîtrisée d'une
    panne invisible.

    ⚠️ Réserve connue, non traitée ici : `db_log_task(..., error=str(e))`
    enregistre le MESSAGE de l'exception. Sur les tâches qui manipulent
    des documents personnels (indexation RAG), ce message peut embarquer
    du contenu réel — même motif que les fuites du 04/08 (`CLAUDE.md`,
    « jamais afficher le contenu d'un fichier de données personnelles »).
    Les deux corrections du 06/08 ne journalisent que le TYPE ; aligner
    les sept autres demande de vérifier ce que chacune perd en
    diagnostic, ce qui dépasse un chantier de lint.
    """

    def __init__(self):
        self.running = True
        self.tasks_completed_today = 0
        self._monitor = None  # SecurityMonitor, chargé au premier balayage
        init_db()
        log("🌌 Lucas Daemon initialisé.")

    # ── 1. Entraînement LoRA ────────────────────────────────
    def nightly_lora_training(self):
        """Entraîne un LoRA sur les conversations du jour."""
        log("🌙 [TÂCHE] Démarrage entraînement LoRA...")
        db_log_task("lora_training", "started")
        start = time.time()
        try:
            # Vérifier qu'il y a assez de données
            conv_dir = DATA_DIR / "conversations"
            if not conv_dir.exists() or len(list(conv_dir.glob("*.json"))) < 10:
                log("⚠️ Pas assez de conversations pour entraîner (< 10). Skip.")
                db_log_task("lora_training", "skipped", "Pas assez de données")
                return

            # Script d'entraînement (à adapter selon ta config axolotl/unsloth)
            training_script = TRAINING_DIR / "train_lora.py"
            if training_script.exists():
                result = subprocess.run(
                    [sys.executable, str(training_script)],
                    capture_output=True, text=True, timeout=3600,
                    check=False,  # le code de retour est inspecté juste après
                )
                if result.returncode == 0:
                    duration = time.time() - start
                    log(f"✅ LoRA entraîné en {duration:.0f}s")
                    db_log_task("lora_training", "success", f"Durée: {duration:.0f}s")
                else:
                    log(f"❌ Erreur LoRA: {result.stderr[:500]}")
                    db_log_task("lora_training", "failed", error=result.stderr[:500])
            else:
                log("⚠️ Script train_lora.py non trouvé. Skip.")
                db_log_task("lora_training", "skipped", "Script non trouvé")
        except Exception as e:  # noqa: BLE001 — voir « Pourquoi ces except Exception » en tete de LucasDaemon
            log(f"❌ Exception LoRA: {e}")
            db_log_task("lora_training", "failed", error=str(e))

    # ── 2. Indexation RAG ───────────────────────────────────
    def index_documents(self):
        """Indexe les nouveaux documents dans ChromaDB."""
        log("📚 [TÂCHE] Indexation documents RAG...")
        db_log_task("rag_indexing", "started")
        start = time.time()
        try:
            docs_dir = DATA_DIR / "documents"
            if not docs_dir.exists():
                log("⚠️ Dossier documents/ vide. Skip.")
                db_log_task("rag_indexing", "skipped", "Dossier vide")
                return

            index_script = LUCAS_ROOT / "memory" / "index_documents.py"
            if index_script.exists():
                result = subprocess.run(
                    [sys.executable, str(index_script)],
                    capture_output=True, text=True, timeout=600,
                    check=False,  # le code de retour est inspecté juste après
                )
                duration = time.time() - start
                if result.returncode == 0:
                    log(f"✅ Indexation terminée en {duration:.0f}s")
                    db_log_task("rag_indexing", "success", f"Durée: {duration:.0f}s")
                else:
                    db_log_task("rag_indexing", "failed", error=result.stderr[:500])
            else:
                log("⚠️ Script index_documents.py non trouvé. Skip.")
                db_log_task("rag_indexing", "skipped", "Script non trouvé")
        except Exception as e:  # noqa: BLE001 — voir « Pourquoi ces except Exception » en tete de LucasDaemon
            log(f"❌ Exception RAG: {e}")
            db_log_task("rag_indexing", "failed", error=str(e))

    # ── 3. Cleanup nocturne ─────────────────────────────────
    def nightly_cleanup(self):
        """Nettoie cache, logs vieux, optimise DB."""
        log("🧹 [TÂCHE] Cleanup nocturne...")
        db_log_task("cleanup", "started")
        try:
            # Supprimer screenshots de +7 jours
            cutoff = datetime.now() - timedelta(days=7)
            deleted = 0
            for f in SCREENSHOTS_DIR.glob("*.png"):
                if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                    f.unlink()
                    deleted += 1
            log(f"🗑️ {deleted} screenshots anciens supprimés")

            # Vider cache Python
            cache_dirs = list(LUCAS_ROOT.rglob("__pycache__"))
            for d in cache_dirs:
                import shutil
                shutil.rmtree(d, ignore_errors=True)
            log(f"🗑️ {len(cache_dirs)} dossiers __pycache__ supprimés")

            # Optimiser SQLite
            conn = sqlite3.connect(DB_FILE)
            conn.execute("VACUUM")
            conn.close()
            log("✅ Base de données optimisée (VACUUM)")

            db_log_task("cleanup", "success", f"Screenshots: {deleted}, Cache: {len(cache_dirs)}")
        except Exception as e:  # noqa: BLE001 — voir « Pourquoi ces except Exception » en tete de LucasDaemon
            log(f"❌ Exception cleanup: {e}")
            db_log_task("cleanup", "failed", error=str(e))

    # ── 4. Screenshots Time Travel ──────────────────────────
    def capture_screenshot(self):
        """Capture l'écran toutes les 30 secondes."""
        try:
            import hashlib

            import pyautogui

            timestamp = datetime.now()
            date_dir = SCREENSHOTS_DIR / timestamp.strftime("%Y-%m-%d")
            date_dir.mkdir(exist_ok=True)

            filename = timestamp.strftime("%H-%M-%S") + ".png"
            filepath = date_dir / filename

            screenshot = pyautogui.screenshot()
            screenshot.save(filepath)

            # Hash pour détecter doublons
            img_hash = hashlib.md5(screenshot.tobytes()).hexdigest()[:16]

            # Détecter fenêtre active (Windows)
            try:
                import win32gui
                hwnd = win32gui.GetForegroundWindow()
                app_name = win32gui.GetWindowText(hwnd)
            except Exception:  # noqa: BLE001 — voir « Pourquoi ces except Exception » en tete de LucasDaemon
                app_name = "unknown"

            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("""
                INSERT INTO screenshots (timestamp, filepath, app_active, hash)
                VALUES (?, ?, ?, ?)
            """, (timestamp.isoformat(), str(filepath), app_name, img_hash))
            conn.commit()
            conn.close()
        except Exception as e:  # noqa: BLE001 — une capture ratée ne doit
            # pas arrêter le daemon, mais elle ne doit pas non plus
            # disparaître : muet, un verrou SQLite ou un disque plein
            # tuerait la fonctionnalité entière sans le moindre signe.
            # Seul le TYPE est journalisé — le message d'une exception
            # SQLite peut embarquer des valeurs de ligne (CLAUDE.md,
            # « jamais afficher le contenu d'un fichier personnel »).
            log(f"⚠️ Enregistrement du screenshot échoué : {type(e).__name__}", "WARN")

    # ── 5. Log émotionnel webcam ────────────────────────────
    def log_emotion(self):
        """Capture émotion via webcam toutes les 5 min."""
        try:
            import cv2
            import numpy as np

            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return

            ret, frame = cap.read()
            cap.release()
            if not ret:
                return

            # Analyse simple : luminosité moyenne = proxy fatigue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness = np.mean(gray)

            if brightness < 50:
                emotion = "dark_room"
            elif brightness < 100:
                emotion = "dim_light"
            else:
                emotion = "well_lit"

            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("""
                INSERT INTO emotional_logs (timestamp, emotion, confidence, source)
                VALUES (?, ?, ?, ?)
            """, (datetime.now().isoformat(), emotion, 0.5, "webcam_brightness"))
            conn.commit()
            conn.close()
        except Exception as e:  # noqa: BLE001 — même motif que ci-dessus :
            # ne pas arrêter le daemon, mais ne pas non plus s'éteindre
            # sans bruit. Type seul, jamais le message.
            log(f"⚠️ Enregistrement du log émotionnel échoué : {type(e).__name__}", "WARN")

    # ── 6. Tests auto ───────────────────────────────────────
    def run_tests(self):
        """Exécute pytest toutes les heures."""
        log("🧪 [TÂCHE] Tests automatiques...")
        db_log_task("auto_tests", "started")
        try:
            # ⚠️ TÂCHE MORTE DEPUIS TOUJOURS — constaté le 06/08/2026.
            # `tests/` n'existe pas dans ce projet : les 49 fichiers
            # `test_*.py` sont à la RACINE (voir CLAUDE.md, § Structure
            # Dossiers : « tous à la racine, pas dans tests/ »). Cette
            # tâche part donc en "skipped" à chaque heure depuis sa
            # création, sans que rien ne le signale.
            #
            # Volontairement NON réparé ici : pointer pytest sur la racine
            # lancerait 1297 tests toutes les heures sur la machine de
            # Cyril, avec un coût CPU réel et un risque d'interférence
            # (plusieurs tests écrivent en base). C'est sa décision, pas
            # un correctif de lint. Voir ROADMAP.md §5.59.
            tests_dir = LUCAS_ROOT / "tests"
            if not tests_dir.exists():
                db_log_task("auto_tests", "skipped", "Dossier tests/ non trouvé")
                return

            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(tests_dir), "-v", "--tb=short"],
                capture_output=True, text=True, timeout=300,
                cwd=str(LUCAS_ROOT),
                check=False,  # le code de retour est inspecté juste après
            )
            if result.returncode == 0:
                log("✅ Tous les tests passent")
                db_log_task("auto_tests", "success", "All tests passed")
            else:
                log(f"⚠️ Tests en échec: {result.stdout[:500]}")
                db_log_task("auto_tests", "failed", error=result.stdout[:1000])
        except Exception as e:  # noqa: BLE001 — voir « Pourquoi ces except Exception » en tete de LucasDaemon
            log(f"❌ Exception tests: {e}")
            db_log_task("auto_tests", "failed", error=str(e))

    # ── 7. Surveillance sécurité continue ───────────────────
    #
    # Observation seule : les capteurs détectent et rapportent, ils
    # n'agissent jamais (VISION_LONG_TERME.md §4.1). Le moniteur ne
    # signale que les nouveautés — un signal permanent et légitime ne
    # doit pas revenir toutes les cinq minutes.

    def _security_monitor(self):
        """Créé à la demande : évite de charger security/ si inutilisé."""
        if self._monitor is None:
            from security import SecurityMonitor

            self._monitor = SecurityMonitor(log_event=self._save_security_event)
        return self._monitor

    def _save_security_event(self, event_type: str, details: str = ""):
        """
        Les signaux vont dans memory/lucas_memory.db, pas dans la base du
        daemon : c'est cette table que Luca's injecte dans son contexte.
        Un capteur dont personne ne lit les résultats ne sert à rien.

        Délègue à la fonction partagée, qui ouvre sa propre connexion
        SQLite. Le daemon en avait sa copie ; l'UI a fini par en avoir
        besoin aussi, et deux implémentations du même geste finissent
        toujours par diverger.
        """
        from memory.memory_manager import save_event_from_any_thread

        if not save_event_from_any_thread(event_type, details):
            log(f"⚠️ Événement sécurité non enregistré : {event_type}", "WARN")

    def _run_security_scan(self, task_name: str, scan):
        """Tronc commun des deux balayages : journalisation et garde-fous."""
        db_log_task(task_name, "started")
        try:
            findings = scan()
        except Exception as e:  # noqa: BLE001 — voir « Pourquoi ces except Exception » en tete de LucasDaemon
            log(f"❌ Balayage {task_name} en échec : {e}", "ERROR")
            db_log_task(task_name, "failed", error=str(e))
            return

        if not findings:
            db_log_task(task_name, "success", "Aucun signal nouveau")
            return

        # La gravité du capteur pilote le niveau de log : un signal INFO
        # écrit en WARN ferait passer du bruit pour une alerte.
        levels = {"info": "INFO", "warning": "WARN", "critical": "ERROR"}
        for finding in findings:
            log(f"🛡️ {finding.summary}", levels.get(finding.severity, "INFO"))
        db_log_task(task_name, "success", f"{len(findings)} signal(s) nouveau(x)")

    def security_scan_runtime(self):
        """Process et connexions réseau — rapide."""
        self._run_security_scan("security_runtime", self._security_monitor().scan_runtime)

    def security_scan_filesystem(self):
        """Fichiers : rançongiciel, appâts — plus lent, donc plus espacé."""
        self._run_security_scan("security_filesystem", self._security_monitor().scan_filesystem)

    # ── 8. Rapport matinal ──────────────────────────────────
    def generate_morning_report(self):
        """Génère un rapport résumé de la nuit."""
        log("📧 [TÂCHE] Génération rapport matinal...")
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()

            # Stats de la nuit
            last_night = (datetime.now() - timedelta(hours=10)).isoformat()
            c.execute("""
                SELECT task_name, status, COUNT(*) FROM daemon_runs
                WHERE started_at > ?
                GROUP BY task_name, status
            """, (last_night,))
            tasks = c.fetchall()

            # Screenshots
            c.execute("SELECT COUNT(*) FROM screenshots WHERE timestamp > ?", (last_night,))
            screenshot_count = c.fetchone()[0]

            # Émotions
            c.execute("SELECT emotion, COUNT(*) FROM emotional_logs WHERE timestamp > ? GROUP BY emotion", (last_night,))
            emotions = c.fetchall()

            conn.close()

            report = f"""
╔══════════════════════════════════════════════════════════════╗
║           🌌 LUCA'S AI — RAPPORT MATINAL                     ║
║           {datetime.now().strftime("%Y-%m-%d %H:%M")}                           ║
╠══════════════════════════════════════════════════════════════╣

📊 TÂCHES NOCTURNES :
"""
            for task, status, count in tasks:
                icon = "✅" if status == "success" else "⚠️" if status == "skipped" else "❌"
                report += f"   {icon} {task}: {status} (x{count})\n"

            report += f"\n📸 Screenshots capturés : {screenshot_count}\n"
            report += "\n😶 Émotions détectées :\n"
            for emotion, count in emotions:
                report += f"   • {emotion}: {count} fois\n"

            report += """
╠══════════════════════════════════════════════════════════════╣
║  💡 Conseil du jour : Continue sur ta lancée !               ║
╚══════════════════════════════════════════════════════════════╝
"""
            report_path = REPORTS_DIR / f"report_{datetime.now().strftime('%Y%m%d')}.txt"
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report)

            log(f"📧 Rapport sauvegardé: {report_path}")
            db_log_task("morning_report", "success", f"Fichier: {report_path}")

            # Afficher dans la console aussi
            print(report)
        except Exception as e:  # noqa: BLE001 — voir « Pourquoi ces except Exception » en tete de LucasDaemon
            log(f"❌ Exception rapport: {e}")
            db_log_task("morning_report", "failed", error=str(e))

    # ─── PLANNING ────────────────────────────────────────────
    def setup_schedule(self):
        """Configure le planning des tâches."""
        # Tâches nocturnes (02h-04h)
        schedule.every().day.at("02:00").do(self.nightly_lora_training)
        schedule.every().day.at("03:00").do(self.index_documents)
        schedule.every().day.at("04:00").do(self.nightly_cleanup)

        # Tâches régulières
        schedule.every(30).seconds.do(self.capture_screenshot)
        schedule.every(5).minutes.do(self.log_emotion)
        schedule.every().hour.do(self.run_tests)

        # Surveillance sécurité. Deux cadences : le runtime est peu coûteux,
        # le balayage fichiers parcourt ~9000 entrées et mérite d'être espacé.
        schedule.every(5).minutes.do(self.security_scan_runtime)
        schedule.every(15).minutes.do(self.security_scan_filesystem)

        # Rapport matinal
        schedule.every().day.at("08:00").do(self.generate_morning_report)

        log("📅 Planning configuré.")
        log("   • 02h00 : Entraînement LoRA")
        log("   • 03h00 : Indexation RAG")
        log("   • 04h00 : Cleanup nocturne")
        log("   • Toutes les 30s : Screenshot")
        log("   • Toutes les 5min : Log émotion")
        log("   • Toutes les 5min : Sécurité — process et réseau")
        log("   • Toutes les 15min : Sécurité — fichiers (rançongiciel)")
        log("   • Toutes les heures : Tests auto")
        log("   • 08h00 : Rapport matinal")

    def run(self):
        """Boucle principale du daemon."""
        self.setup_schedule()
        log("🚀 Lucas Daemon démarré. Ctrl+C pour arrêter.")
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            log("👋 Arrêt du daemon demandé.")
            self.running = False


if __name__ == "__main__":
    daemon = LucasDaemon()
    daemon.run()
