"""
Orion Daemon — Cerveau nocturne d'Orion AI
Tourne 24/7 en arrière-plan sur le PC maître.
Gère : entraînement LoRA, indexation RAG, screenshots, cleanup, logs émotionnels.

Lancement :
    pythonw orion_daemon.py          (Windows, sans fenêtre)
    ou : nssm install OrionDaemon ... (service Windows)

Auteur : Orion AI Project
"""

import os
import sys
import time
import json
import asyncio
import sqlite3
import subprocess
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from threading import Thread
import schedule

# ─── CONFIGURATION ─────────────────────────────────────────
ORION_ROOT = Path("C:/OrionAI")
DATA_DIR = ORION_ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
MODELS_DIR = ORION_ROOT / "models"
TRAINING_DIR = ORION_ROOT / "training"
REPORTS_DIR = DATA_DIR / "reports"

# Créer les dossiers manquants
for d in [DATA_DIR, LOGS_DIR, SCREENSHOTS_DIR, MODELS_DIR, TRAINING_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOGS_DIR / "daemon.log"
DB_FILE = DATA_DIR / "orion_daemon.db"
CONFIG_FILE = ORION_ROOT / "config.json"

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

class OrionDaemon:
    """Daemon principal d'Orion AI."""

    def __init__(self):
        self.running = True
        self.tasks_completed_today = 0
        init_db()
        log("🌌 Orion Daemon initialisé.")

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
                    capture_output=True, text=True, timeout=3600
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
        except Exception as e:
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

            index_script = ORION_ROOT / "memory" / "index_documents.py"
            if index_script.exists():
                result = subprocess.run(
                    [sys.executable, str(index_script)],
                    capture_output=True, text=True, timeout=600
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
        except Exception as e:
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
            cache_dirs = list(ORION_ROOT.rglob("__pycache__"))
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
        except Exception as e:
            log(f"❌ Exception cleanup: {e}")
            db_log_task("cleanup", "failed", error=str(e))

    # ── 4. Screenshots Time Travel ──────────────────────────
    def capture_screenshot(self):
        """Capture l'écran toutes les 30 secondes."""
        try:
            from PIL import Image
            import pyautogui
            import hashlib

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
            except:
                app_name = "unknown"

            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("""
                INSERT INTO screenshots (timestamp, filepath, app_active, hash)
                VALUES (?, ?, ?, ?)
            """, (timestamp.isoformat(), str(filepath), app_name, img_hash))
            conn.commit()
            conn.close()
        except Exception as e:
            # Silencieux pour ne pas spammer les logs
            pass

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
        except Exception:
            pass

    # ── 6. Tests auto ───────────────────────────────────────
    def run_tests(self):
        """Exécute pytest toutes les heures."""
        log("🧪 [TÂCHE] Tests automatiques...")
        db_log_task("auto_tests", "started")
        try:
            tests_dir = ORION_ROOT / "tests"
            if not tests_dir.exists():
                db_log_task("auto_tests", "skipped", "Dossier tests/ non trouvé")
                return

            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(tests_dir), "-v", "--tb=short"],
                capture_output=True, text=True, timeout=300,
                cwd=str(ORION_ROOT)
            )
            if result.returncode == 0:
                log("✅ Tous les tests passent")
                db_log_task("auto_tests", "success", "All tests passed")
            else:
                log(f"⚠️ Tests en échec: {result.stdout[:500]}")
                db_log_task("auto_tests", "failed", error=result.stdout[:1000])
        except Exception as e:
            log(f"❌ Exception tests: {e}")
            db_log_task("auto_tests", "failed", error=str(e))

    # ── 7. Rapport matinal ──────────────────────────────────
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
║           🌌 ORION AI — RAPPORT MATINAL                      ║
║           {datetime.now().strftime("%Y-%m-%d %H:%M")}                           ║
╠══════════════════════════════════════════════════════════════╣

📊 TÂCHES NOCTURNES :
"""
            for task, status, count in tasks:
                icon = "✅" if status == "success" else "⚠️" if status == "skipped" else "❌"
                report += f"   {icon} {task}: {status} (x{count})\n"

            report += f"\n📸 Screenshots capturés : {screenshot_count}\n"
            report += f"\n😶 Émotions détectées :\n"
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
        except Exception as e:
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

        # Rapport matinal
        schedule.every().day.at("08:00").do(self.generate_morning_report)

        log("📅 Planning configuré.")
        log("   • 02h00 : Entraînement LoRA")
        log("   • 03h00 : Indexation RAG")
        log("   • 04h00 : Cleanup nocturne")
        log("   • Toutes les 30s : Screenshot")
        log("   • Toutes les 5min : Log émotion")
        log("   • Toutes les heures : Tests auto")
        log("   • 08h00 : Rapport matinal")

    def run(self):
        """Boucle principale du daemon."""
        self.setup_schedule()
        log("🚀 Orion Daemon démarré. Ctrl+C pour arrêter.")
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            log("👋 Arrêt du daemon demandé.")
            self.running = False


if __name__ == "__main__":
    daemon = OrionDaemon()
    daemon.run()
