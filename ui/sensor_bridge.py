# ui/sensor_bridge.py — pont capteurs téléphone → session PC (12/08/2026)
#
# Brief : cowork_workspace/BRIEF_PONT_CAPTEURS_TELEPHONE_PC.md
#
# Le PC n'a ni micro ni webcam (D-6, matériel pas encore acheté). En
# attendant, le téléphone sert de capteur : Cyril parle ou photographie
# depuis la PWA, et le tour de conversation arrive ICI, dans la session
# desktop, au lieu de rester dans la boucle mobile.
#
# ⚠️ Ce pont est en LECTURE SEULE sur la conversation. Il ne pose jamais
# de question à LucasCore : le serveur a déjà traité le tour (transcription
# Whisper, routage, réponse, mémoire) avant de le relayer. Rappeler ask()
# ici produirait une seconde réponse à la même question, et une seconde
# ligne dans l'historique partagé.
#
# ── Pourquoi un WebSocket plutôt que relire la base ───────────────────
#
# L'historique EST déjà partagé : desktop, PWA et daemon écrivent tous
# dans memory/lucas_memory.db, table `conversations`, sans distinction de
# client. Ce que dit Cyril au téléphone est donc DÉJÀ dans la base — mais
# `_load_history()` n'est appelé qu'à la construction de la fenêtre
# (ui/main_window.py), et rien ne notifie une écriture : un message
# mobile restait invisible jusqu'au prochain redémarrage de l'app.
#
# Interroger la base en boucle aurait été le réflexe simple. Écarté : le
# serveur sait déjà exactement quand un tour se termine, et sa réponse
# transite déjà par un WebSocket. Un sondage aurait ajouté une source de
# vérité concurrente, avec sa latence propre, pour redécouvrir après coup
# ce que le serveur pouvait dire à l'instant même.
#
# ── Certificat ────────────────────────────────────────────────────────
#
# Le serveur écoute en HTTPS avec un certificat mkcert (tools/mkcert.exe),
# dont l'autorité racine est installée dans le magasin Windows. VÉRIFIÉ
# réellement le 12/08/2026 : Qt valide ce certificat sans la moindre
# exception (aucun signal sslErrors émis). Aucun assouplissement n'est
# donc posé ici — ni ignoreSslErrors(), ni écoute en clair. Si un jour la
# connexion échoue en TLS, la bonne réponse sera de réinstaller la CA
# mkcert, jamais de désactiver la vérification.

from __future__ import annotations

import json

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtWebSockets import QWebSocket, QWebSocketHandshakeOptions

from config import API_PORT, API_TOKEN

# Doivent rester identiques à WS_SUBPROTOCOL / WS_TOKEN_SUBPROTOCOL_PREFIX
# (api/server.py) et à leurs jumeaux de static/js/websocket.js.
WS_SUBPROTOCOL = "lucas.v1"
WS_TOKEN_SUBPROTOCOL_PREFIX = "lucas-token."

# 127.0.0.1 et jamais l'adresse réseau : les deux processus tournent sur
# la même machine, ce lien n'a aucune raison de sortir de la boucle
# locale (RT-3, tout reste local).
WS_URL = f"wss://127.0.0.1:{API_PORT}/ws"

# Le serveur peut démarrer après l'app desktop (tâches planifiées
# indépendantes) — réessayer sans fin plutôt qu'échouer une fois et
# rester muet. Même délai que la PWA (static/js/websocket.js).
RECONNECT_DELAY_MS = 3000


class SensorBridge(QObject):
    """
    Écoute ce que le téléphone capte pour le compte du PC.

    Trois signaux, volontairement pauvres : ce pont ne décide de rien, il
    traduit des messages WebSocket en événements Qt. Toute la logique
    d'affichage reste dans MainWindow, qui sait déjà écrire dans le chat
    et parler — dupliquer ça ici créerait un second chemin d'affichage à
    maintenir en parallèle du premier.
    """

    # (role, texte) — role vaut "user" ou "assistant", comme la colonne
    # `role` de la table conversations : MainWindow peut le passer tel
    # quel à son _append() existant.
    message_received = Signal(str, str)
    # Réponse à prononcer sur les enceintes du PC (Cyril a choisi la
    # sortie « PC » côté téléphone). Séparé de message_received : la
    # plupart des réponses ne doivent PAS être prononcées ici.
    speak_requested = Signal(str)
    # Le mode capteur vient d'être allumé/éteint côté téléphone.
    sensor_mode_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._socket = QWebSocket()
        self._socket.connected.connect(self._on_connected)
        self._socket.textMessageReceived.connect(self._on_text)
        self._socket.disconnected.connect(self._schedule_reconnect)
        self._closing = False
        self._connect()

    # ── Connexion ────────────────────────────────────────────────────

    def _connect(self):
        options = QWebSocketHandshakeOptions()
        protocols = [WS_SUBPROTOCOL]
        # Le jeton voyage dans les sous-protocoles, donc dans un en-tête
        # standard — jamais dans la query string, qui atterrirait en clair
        # dans data/logs/server_startup.log (même raison que la PWA, voir
        # api/server.py). Absent tant que Cyril n'a rien configuré.
        if API_TOKEN:
            protocols.append(WS_TOKEN_SUBPROTOCOL_PREFIX + API_TOKEN)
        options.setSubprotocols(protocols)
        self._socket.open(QUrl(WS_URL), options)

    def _on_connected(self):
        # Ce "hello" est ce qui inscrit la session dans le registre des
        # clients desktop côté serveur : sans lui, la connexion est
        # ouverte mais ne reçoit jamais rien du pont.
        self._send({"type": "hello", "client": "lucas_desktop", "version": "1.0"})

    def _schedule_reconnect(self):
        # Pas de reconnexion après un close() volontaire : la fenêtre est
        # en train de se fermer, rouvrir un socket ferait vivre un timer
        # au-delà de l'application.
        if self._closing:
            return
        QTimer.singleShot(RECONNECT_DELAY_MS, self._connect)

    def _send(self, payload: dict):
        self._socket.sendTextMessage(json.dumps(payload))

    # ── Réception ────────────────────────────────────────────────────

    def _on_text(self, raw: str):
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            # Un message illisible ne doit pas tuer le pont : la session
            # continue, ce message-là est perdu.
            return
        if not isinstance(data, dict):
            return

        message_type = data.get("type")
        if message_type == "sensor_message":
            role = data.get("role", "assistant")
            text = data.get("text", "")
            if not text:
                return
            self.message_received.emit(role, text)
            if role == "assistant" and data.get("speak_here"):
                self.speak_requested.emit(text)
        elif message_type == "sensor_status":
            self.sensor_mode_changed.emit(bool(data.get("active")))
        # Tout le reste (avatar_state, system, security_status, chat,
        # speech...) est ignoré SANS erreur : cette session n'est pas un
        # client de conversation, elle n'écoute que le pont. Les
        # pousseurs de fond du serveur continuent d'émettre pour elle,
        # c'est sans conséquence.

    def close(self):
        """Ferme proprement — appelé à la fermeture de la fenêtre."""
        self._closing = True
        self._socket.close()
