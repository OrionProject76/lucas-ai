# ui/main_window.py — interface Luca's
# Avatar animé + TTS auto + Streaming fluide + HUD dark

from PySide6.QtCore import (
    Q_ARG,
    Q_RETURN_ARG,
    QMetaObject,
    QObject,
    Qt,
    QThread,
    Signal,
    Slot,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import WINDOW_HEIGHT, WINDOW_TITLE, WINDOW_WIDTH
from core.llm_worker import LLMWorker
from core.lucas_core import LucasCore
from core.router import should_use_vision
from memory.memory_manager import save_event_from_any_thread
from modules.stt_engine import STTEngine, STTUnavailable

# Instance unique, partagée entre toutes les transcriptions du bouton
# micro — recharger Whisper à chaque fichier serait coûteux (même
# raisonnement que _stt_engine dans api/server.py, pont mobile). Ce
# module est le second et dernier appelant réel de modules/stt_engine.py,
# jamais un second pipeline parallèle.
_stt_engine = STTEngine()

# ── Imports optionnels — fallback gracieux ──
try:
    from ui.avatar_widget import AvatarWidget
    HAS_AVATAR = True
except ImportError:
    HAS_AVATAR = False

try:
    from modules.voice_manager import SENSITIVE_SKIPPED_MESSAGE, VoiceManager
    HAS_VOICE = True
except ImportError:
    HAS_VOICE = False
    SENSITIVE_SKIPPED_MESSAGE = "[Voix] Contenu sensible non prononcé."


DARK_STYLE = """
QWidget {
    background-color: #0D0D12;
    color: #E8EAED;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 14px;
}
QTextEdit {
    background-color: #14141A;
    border: 1px solid #2A2C38;
    border-radius: 10px;
    padding: 12px;
    color: #E8EAED;
    line-height: 1.5;
}
QLineEdit {
    background-color: #14141A;
    border: 1px solid #2A2C38;
    border-radius: 10px;
    padding: 10px 14px;
    color: #E8EAED;
    font-size: 14px;
}
QLineEdit:focus {
    border: 1px solid #00D4FF;
}
QPushButton {
    background-color: #1E88E5;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 14px;
}
QPushButton:hover {
    background-color: #00D4FF;
}
QPushButton:disabled {
    background-color: #2A2C38;
    color: #6B6F7B;
}
QPushButton#stop {
    background-color: #E53935;
}
QPushButton#stop:hover {
    background-color: #FF5252;
}
QPushButton#tts {
    background-color: #2A2C38;
    color: #6B6F7B;
    border-radius: 10px;
    padding: 8px;
    font-size: 16px;
}
QPushButton#tts:checked {
    background-color: #00D4FF;
    color: #0D0D12;
}
QLabel#title {
    font-size: 22px;
    font-weight: bold;
    color: #00D4FF;
    padding: 10px;
    letter-spacing: 2px;
}
QLabel#status {
    color: #FFB300;
    font-style: italic;
    font-size: 12px;
    padding: 4px 8px;
    background-color: #1A1A24;
    border-radius: 6px;
}
/* Variantes par propriété dynamique et non par objectName : Qt ne
   connaît pas les listes de classes CSS. « status status_connecting »
   ne correspondait à AUCUNE règle, et le libellé perdait fond, marges
   et couleur dès le premier message. Le sélecteur d'attribut, lui,
   s'ajoute à QLabel#status au lieu de le remplacer. */
QLabel#status[variant="connecting"] {
    color: #FFB300;
}
QLabel#status[variant="thinking"] {
    color: #00D4FF;
}
QLabel#status[variant="watching"] {
    color: #FFAA00;
}
"""


class ContextWorker(QThread):
    """
    Construit le contexte du prompt hors du thread principal.

    Nécessaire depuis l'arrivée de la vision : sur « regarde mon écran »,
    le premier chargement de llava en VRAM prend ~25 s. Le faire dans le
    thread UI figerait toute l'interface, sans même un curseur d'attente.

    ⚠️ Le worker crée sa PROPRE instance de LucasCore. SQLite refuse d'être
    utilisé depuis un autre thread que celui qui a ouvert la connexion —
    réutiliser celle de MainWindow lèverait une ProgrammingError. Même
    raison que dans api/server.py, et sans coût : tout l'état vit dans la
    base, pas en mémoire Python.
    """

    ready = Signal(list)
    error = Signal(str)

    def __init__(self, text: str):
        super().__init__()
        self.text = text
        self._cancelled = False

    def cancel(self):
        """
        Abandonne le résultat en cours.

        La construction du contexte ne s'interrompt pas au milieu — une
        analyse VLM déjà lancée va à son terme. Mais si Cyril appuie sur
        Stop, sa réponse ne doit pas surgir vingt secondes plus tard dans
        une interface qu'il croyait libérée.
        """
        self._cancelled = True

    def run(self):
        core = None
        try:
            core = LucasCore()
            messages = core.prepare(self.text)
            if not self._cancelled:
                self.ready.emit(messages)
        except Exception as e:  # noqa: BLE001 — une erreur de contexte
            # doit devenir un message dans le chat, jamais une exception
            # qui remonte dans la boucle Qt et fait tomber la fenêtre.
            if not self._cancelled:
                self.error.emit(f"[Erreur] Préparation du contexte impossible : {e}")
        finally:
            if core is not None:
                core.close()


class TTSWorker(QThread):
    """Thread séparé pour la synthèse vocale — ne bloque jamais l'UI."""
    finished = Signal()
    error = Signal(str)
    # Émis quand le son démarre réellement, pas quand la synthèse est
    # lancée : edge_tts passe par le réseau et met plusieurs secondes.
    playback_started = Signal()

    def __init__(self, text: str, question: str = "", log_event=None):
        super().__init__()
        self.text = text
        self.question = question
        self.log_event = log_event

    def run(self):
        try:
            if HAS_VOICE:
                vm = VoiceManager(log_event=self.log_event)
                # speak() route entre Piper (local) et edge_tts (cloud) selon
                # la sensibilité du contenu — voir CLAUDE.md règle 3.
                spoken = vm.speak(
                    self.text,
                    self.question,
                    on_playback_start=self.playback_started.emit,
                )
                if spoken is None:
                    self.error.emit(SENSITIVE_SKIPPED_MESSAGE)
            else:
                self.error.emit("Module voix non disponible")
        except Exception as e:  # noqa: BLE001 — un souci de synthèse ne
            # doit pas faire tomber le thread ni l'interface.
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class STTWorker(QThread):
    """
    Transcrit un fichier audio dans un thread séparé — ne bloque jamais l'UI.

    ⚠️ Ce PC n'a pas de microphone (VISION_LONG_TERME.md §2, Pilier 3) :
    ce worker transcrit un fichier déjà enregistré, choisi via un
    sélecteur de fichier — ce n'est PAS une capture micro en direct.
    Utilise le MÊME STTEngine partagé que le pont mobile (api/server.py) :
    jamais un second pipeline de transcription.
    """

    transcribed = Signal(str)
    error = Signal(str)

    def __init__(self, audio_path: str):
        super().__init__()
        self.audio_path = audio_path

    def run(self):
        try:
            result = _stt_engine.transcribe(self.audio_path)
            self.transcribed.emit(result.text)
        except STTUnavailable as e:
            self.error.emit(f"Transcription impossible : {e}")
        except Exception as e:  # noqa: BLE001 — un souci de transcription ne
            # doit pas faire tomber le thread ni l'interface.
            self.error.emit(str(e))


class ConfirmationBridge(QObject):
    """
    Pont de confirmation pour core/os_controller.py (Brique 2, 08/08/2026).

    Un QMessageBox ne peut s'afficher que sur le thread GUI, mais
    OSController est généralement appelé depuis le QThread worker qui
    exécute LucasCore.ask() (même contrainte que le streaming du chat). Ce
    pont vit sur le thread GUI ; MainWindow.confirm_destructive() (plus
    bas) l'invoque en toute sécurité depuis n'importe quel thread.
    """

    @Slot(str, result=bool)
    def confirm_destructive_action(self, message: str) -> bool:
        reply = QMessageBox.question(
            None,
            "Confirmer l'action",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.lucas = LucasCore()
        self._confirmation_bridge = ConfirmationBridge()
        self.worker = None
        self.tts_worker = None
        self.context_worker = None
        self.stt_worker = None
        self.tts_auto = False
        self.last_lucas_response = ""

        self.setWindowTitle(WINDOW_TITLE)
        self.resize(WINDOW_WIDTH + 180, WINDOW_HEIGHT)
        self.setStyleSheet(DARK_STYLE)

        # ═══════════════════════════════════════════════
        #  LAYOUT PRINCIPAL HORIZONTAL : Avatar | Chat
        # ═══════════════════════════════════════════════
        main_layout = QHBoxLayout()
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # ── Panel gauche : Avatar ──
        left_layout = QVBoxLayout()
        left_layout.setSpacing(8)
        left_layout.setContentsMargins(8, 16, 8, 16)

        # Annoté avant la branche : sans ça, mypy fige le type sur la
        # première affectation (`AvatarWidget`) et refuse le `None` de
        # l'autre branche. L'avatar EST optionnel — c'est tout le sens du
        # repli quand son import échoue.
        self.avatar: AvatarWidget | None
        if HAS_AVATAR:
            self.avatar = AvatarWidget()
            self.avatar.setFixedSize(140, 140)
            left_layout.addWidget(self.avatar, alignment=Qt.AlignmentFlag.AlignCenter)
        else:
            self.avatar = None
            placeholder = QLabel("◈")
            placeholder.setStyleSheet("font-size: 48px; color: #00D4FF;")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            left_layout.addWidget(placeholder)

        self.avatar_status = QLabel("● En ligne")
        self.avatar_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_status.setStyleSheet(
            "color: #00D4FF; font-size: 11px; font-weight: bold;"
        )
        left_layout.addWidget(self.avatar_status)
        left_layout.addStretch()

        left_container = QWidget()
        left_container.setLayout(left_layout)
        left_container.setFixedWidth(170)
        left_container.setStyleSheet("""
            QWidget {
                background-color: #0A0A0F;
                border: 1px solid #1E1E28;
                border-radius: 16px;
            }
        """)

        # ── Panel droit : Chat ──
        right_layout = QVBoxLayout()
        right_layout.setSpacing(12)

        # Titre
        title = QLabel("◈ LUCA'S ◈")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Zone de chat
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Barre de statut
        self.status_label = QLabel("")
        self.status_label.setObjectName("status")
        self.status_label.setVisible(False)

        # Zone de saisie + boutons
        input_layout = QHBoxLayout()

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Parle à Luca's...")
        self.input_field.returnPressed.connect(self.send_message)
        self.input_field.textChanged.connect(self._on_typing)

        self.send_button = QPushButton("Envoyer")
        self.send_button.setFixedWidth(100)
        self.send_button.clicked.connect(self.send_message)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("stop")
        self.stop_button.setFixedWidth(80)
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.stop_generation)

        # 🔊 Bouton TTS Auto (toggle)
        self.tts_button = QPushButton("🔇")
        self.tts_button.setObjectName("tts")
        self.tts_button.setCheckable(True)
        self.tts_button.setFixedWidth(40)
        self.tts_button.setToolTip("TTS Auto — Luca's lit ses réponses")
        self.tts_button.clicked.connect(self.toggle_tts)

        # 🎙️ Bouton STT — transcrit un fichier audio, PAS une capture micro
        # en direct (ce PC n'a pas de microphone, voir STTWorker).
        self.mic_button = QPushButton("🎙️")
        self.mic_button.setObjectName("tts")
        self.mic_button.setFixedWidth(40)
        self.mic_button.setToolTip(
            "Transcrire un fichier audio (pas de micro sur ce PC — pont mobile S25 Ultra)"
        )
        self.mic_button.clicked.connect(self.transcribe_audio_file)

        input_layout.addWidget(self.input_field, stretch=1)
        input_layout.addWidget(self.send_button)
        input_layout.addWidget(self.stop_button)
        input_layout.addWidget(self.mic_button)
        input_layout.addWidget(self.tts_button)

        # Assemblage droit
        right_layout.addWidget(title)
        right_layout.addWidget(self.chat_history, stretch=1)
        right_layout.addWidget(self.status_label)
        right_layout.addLayout(input_layout)

        right_container = QWidget()
        right_container.setLayout(right_layout)

        # Assemblage final
        main_layout.addWidget(left_container)
        main_layout.addWidget(right_container, stretch=1)
        self.setLayout(main_layout)

        self._load_history()
        self._set_avatar_state("IDLE")

    # ── Avatar states ──
    def confirm_destructive(self, message: str) -> bool:
        """
        À injecter comme `confirm_destructive` dans core/os_controller.py.

        Sûr depuis n'importe quel thread : si l'appelant est déjà sur le
        thread GUI, appel direct (un `BlockingQueuedConnection` émis vers
        son propre thread ferait un deadlock — son event loop, bloquée en
        attente, ne traiterait jamais l'appel en file). Sinon, invoqué via
        `QMetaObject.invokeMethod` en connexion bloquante : le thread
        appelant attend le résultat, affiché sur le thread GUI.
        """
        app_instance = QApplication.instance()
        assert app_instance is not None, "MainWindow exige une QApplication déjà construite"
        if QThread.currentThread() is app_instance.thread():
            return self._confirmation_bridge.confirm_destructive_action(message)
        return bool(QMetaObject.invokeMethod(
            self._confirmation_bridge,
            "confirm_destructive_action",
            Qt.ConnectionType.BlockingQueuedConnection,
            Q_RETURN_ARG(bool),
            Q_ARG(str, message),
        ))

    def _set_status(self, text: str, variant: str = "connecting"):
        """
        Affiche un message de statut dans la bonne couleur.

        Passe par une propriété dynamique et non par objectName : Qt ne
        connaît pas les listes de classes CSS, et un changement de style
        n'est pris en compte qu'après unpolish/polish. Sans ces deux
        précautions, le libellé perdait fond et couleur dès le premier
        message envoyé.
        """
        self.status_label.setText(text)
        self.status_label.setProperty("variant", variant)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.status_label.setVisible(True)

    def _set_avatar_state(self, state: str):
        """Met à jour l'état visuel de l'avatar + le label de statut."""
        if self.avatar:
            self.avatar.set_state(state)
        # WATCHING manquait : le libellé affichait « En ligne » pendant
        # que l'avatar virait à l'ambre. L'ambre du témoin de capture est
        # repris ici pour que les deux indicateurs disent la même chose.
        states = {
            "IDLE":          ("● En ligne",             "#00D4FF"),
            "LISTENING":     ("● Écoute...",             "#00E676"),
            "THINKING":      ("● Réfléchit...",          "#FFB300"),
            "THINKING_DEEP": ("● Réfléchit plus...",     "#C814FF"),
            "SPEAKING":      ("● Parle...",              "#E040FB"),
            "WATCHING":      ("● Regarde l'écran",       "#FFAA00"),
            "OBSERVING":     ("● Observe l'écran",       "#C88C50"),
        }
        text, color = states.get(state, ("● En ligne", "#00D4FF"))
        self.avatar_status.setText(text)
        self.avatar_status.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: bold;"
        )

    def _on_typing(self):
        """
        Cyril tape : Luca's devient attentive. Champ vidé : elle revient
        au repos.

        Le retour manquait — effacer sa saisie laissait l'avatar en
        LISTENING indéfiniment, y compris après avoir renoncé à écrire.

        Ne s'applique que si aucune génération n'est en cours : sinon un
        effacement pendant que Luca's réfléchit la ferait paraître au
        repos alors qu'elle travaille.
        """
        if not self.avatar:
            return
        if self.worker is not None and self.worker.isRunning():
            return

        if self.input_field.text().strip():
            self._set_avatar_state("LISTENING")
        elif self.avatar.state == "LISTENING":
            self._set_avatar_state("IDLE")

    # ── Chat history ──
    def _load_history(self):
        for role, message in self.lucas.history():
            self._append(role, message)

    def _append(self, role: str, message: str):
        speaker = "Cyril" if role == "user" else "Luca's"
        color = "#00D4FF" if role == "user" else "#E8EAED"
        self.chat_history.append(
            f'<span style="color:{color};"><b>{speaker} :</b></span> {message}'
        )

    # ── Envoi message ──
    def send_message(self):
        text = self.input_field.text().strip()
        if not text:
            return

        self._append("user", text)
        self.input_field.clear()

        # Mémorisé pour le routage TTS : une réponse anodine à une question
        # sensible reste sensible (voir core.router.route_voice).
        self.last_user_message = text

        # UI en mode "attente"
        self.send_button.setVisible(False)
        self.stop_button.setVisible(True)
        self.input_field.setEnabled(False)

        # La construction du contexte peut être longue : sur une question
        # « regarde mon écran », le premier chargement de llava en VRAM
        # prend ~25 s (0,8 s ensuite, modèle chaud). D'où le message
        # explicite plutôt qu'une interface figée sans explication.
        # L'avatar dit ce que Luca's est en train de faire. WATCHING n'est
        # pas cosmétique : c'est le témoin que l'écran est en train d'être
        # capturé, comme la LED d'une webcam.
        # ⚠️ Le MÊME contexte que ContextWorker, via le même helper : le
        # cache de core/intent est indexé sur (contexte, question), donc
        # deux contextes différents pour un seul message donneraient deux
        # appels au classifieur au lieu d'un.
        if should_use_vision(text, self.lucas.recent_context()):
            self._set_status("👁️ Luca's regarde ton écran...", "watching")
            self._set_avatar_state("WATCHING")
        else:
            self._set_status("⏳ Préparation du contexte...", "connecting")
            self._set_avatar_state("THINKING")

        # Le contexte est construit dans un thread : capture d'écran,
        # analyse VLM et requête RAG bloqueraient sinon toute l'interface.
        self.context_worker = ContextWorker(text)
        self.context_worker.ready.connect(self._on_context_ready)
        self.context_worker.error.connect(self._on_error)
        self.context_worker.start()

    def _on_context_ready(self, messages: list):
        """Le contexte est prêt : on peut lancer la génération."""
        self._set_status("⏳ Connexion à Ollama...", "connecting")
        # La capture est terminée : le témoin ambre doit s'éteindre au
        # moment exact où Luca's cesse de regarder.
        self._set_avatar_state("THINKING")

        self.chat_history.append(
            '<span style="color:#E8EAED;"><b>Luca&#39;s :</b></span> '
        )

        # Lancer le worker LLM
        self.worker = LLMWorker(messages)
        self.worker.started_thinking.connect(self._on_started)
        self.worker.token_received.connect(self._on_token)
        self.worker.response_complete.connect(self._on_complete)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.start()

    def _on_started(self):
        self._set_status("💭 Luca's réfléchit...", "thinking")

    def _on_token(self, token: str):
        if self.status_label.isVisible():
            self.status_label.setVisible(False)

        cursor = self.chat_history.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(token)
        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()

    def _on_complete(self, full_answer: str):
        self.last_lucas_response = full_answer
        self.lucas.save_response(full_answer)
        self._unlock_input()

        # 🔊 TTS Auto ?
        if self.tts_auto and full_answer.strip() and HAS_VOICE:
            self._speak(full_answer)
        else:
            self._set_avatar_state("IDLE")

    def _on_error(self, error_message: str):
        self.status_label.setVisible(False)
        self._append("assistant", error_message)
        self._set_avatar_state("IDLE")
        self._unlock_input()

    # ── TTS ──
    def toggle_tts(self, checked: bool):
        """Active/désactive la lecture vocale automatique."""
        self.tts_auto = checked
        self.tts_button.setText("🔊" if checked else "🔇")
        self.tts_button.setToolTip(
            "TTS Auto ON — Luca's parle" if checked else "TTS Auto OFF"
        )

    def _speak(self, text: str):
        """
        Lance la lecture vocale dans un thread séparé.

        L'avatar ne passe PAS en SPEAKING tout de suite : la synthèse
        prend plusieurs secondes avec edge_tts, qui passe par le réseau.
        Le faire ici montrerait Luca's en train de parler pendant un
        silence — l'avatar mentirait sur son état.
        """
        self._set_status("🔊 Synthèse de la voix...", "connecting")
        # ⚠️ PAS self.lucas.log_event : le worker tourne dans un autre
        # thread, et SQLite refuse une connexion ouverte ailleurs. C'est
        # ce qui levait « SQLite objects created in a thread can only be
        # used in that same thread » à chaque lecture vocale.
        self.tts_worker = TTSWorker(
            text,
            getattr(self, "last_user_message", ""),
            save_event_from_any_thread,
        )
        self.tts_worker.playback_started.connect(self._on_playback_started)
        self.tts_worker.finished.connect(self._on_tts_finished)
        self.tts_worker.error.connect(self._on_tts_error)
        self.tts_worker.start()

    def _on_playback_started(self):
        """Le son démarre : c'est maintenant que Luca's parle."""
        self.status_label.setVisible(False)
        self._set_avatar_state("SPEAKING")

    def _on_tts_finished(self):
        self._set_avatar_state("IDLE")

    def _on_tts_error(self, msg: str):
        print(f"[TTS Error] {msg}")
        # Visible pour Cyril : sans ça, un contenu sensible non prononcé
        # passerait pour un simple silence inexpliqué.
        self._append("assistant", msg)
        self._set_avatar_state("IDLE")

    # ── STT (fichier audio, pas de micro sur ce PC) ──
    def transcribe_audio_file(self):
        """
        Transcrit un fichier audio via le même STTEngine que le pont
        mobile (api/server.py) — jamais un second pipeline.

        ⚠️ Pas un bouton micro au sens propre : ce PC n'a pas de
        microphone (VISION_LONG_TERME.md §2, Pilier 3 — c'est le S25
        Ultra qui capte l'audio réel). Le texte transcrit remplit le
        champ de saisie sans envoyer automatiquement : Cyril garde la
        main pour relire ou corriger avant d'envoyer, comme pour tout ce
        qu'il tape lui-même.
        """
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir un fichier audio", "",
            "Fichiers audio (*.wav *.mp3 *.m4a *.ogg *.flac)",
        )
        if not path:
            return

        self._set_status("🎙️ Transcription de l'audio...", "connecting")
        self._set_avatar_state("THINKING")
        self.mic_button.setEnabled(False)

        self.stt_worker = STTWorker(path)
        self.stt_worker.transcribed.connect(self._on_transcribed)
        self.stt_worker.error.connect(self._on_stt_error)
        self.stt_worker.start()

    def _on_transcribed(self, text: str):
        self.status_label.setVisible(False)
        self._set_avatar_state("IDLE")
        self.mic_button.setEnabled(True)
        self.input_field.setText(text)
        self.input_field.setFocus()

    def _on_stt_error(self, message: str):
        self.status_label.setVisible(False)
        self._set_avatar_state("IDLE")
        self.mic_button.setEnabled(True)
        self._append("assistant", f"[STT] {message}")

    # ── Stop & Unlock ──
    def stop_generation(self):
        """
        Interrompt ce qui est en cours, quelle que soit l'étape.

        Le bouton Stop est visible dès l'envoi, y compris pendant la
        construction du contexte — c'est justement la phase la plus
        longue, jusqu'à 25 s au premier chargement de llava. Il ne
        traitait que le worker LLM : appuyer sur Stop pendant l'attente
        la plus pénible ne faisait rien.
        """
        interrupted = False

        if self.context_worker is not None and self.context_worker.isRunning():
            self.context_worker.cancel()
            interrupted = True

        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            interrupted = True

        if interrupted:
            self._append("assistant", "[Génération interrompue]")
            self.status_label.setVisible(False)
            self._set_avatar_state("IDLE")
            self._unlock_input()

    def _unlock_input(self):
        self.send_button.setVisible(True)
        self.stop_button.setVisible(False)
        self.send_button.setEnabled(True)
        self.input_field.setEnabled(True)
        self.input_field.setFocus()

    # ── Fermeture ──
    def closeEvent(self, event):
        # Le ContextWorker peut tenir 25 s sur une analyse VLM. Sans
        # attente, Qt détruit l'objet QThread pendant que le thread
        # tourne encore — « QThread: Destroyed while thread is still
        # running », et l'application peut tomber à la fermeture.
        if self.context_worker is not None and self.context_worker.isRunning():
            self.context_worker.cancel()
            self.context_worker.wait(30000)
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
        if self.tts_worker is not None and self.tts_worker.isRunning():
            self.tts_worker.wait(2000)
        if self.stt_worker is not None and self.stt_worker.isRunning():
            self.stt_worker.wait(2000)
        self.lucas.close()
        event.accept()
