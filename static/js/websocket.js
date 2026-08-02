// static/js/websocket.js — connexion unique vers /ws, protocole api/protocol.py.
//
// Même rôle que Lucas3D/scripts/websocket_client.gd côté Godot : un seul
// canal, un vocabulaire partagé (avatar_state / chat / system / error),
// jamais un protocole parallèle pour la PWA.

window.Lucas = window.Lucas || {};

(function () {
    const RECONNECT_DELAY_MS = 3000;

    class LucasSocket {
        constructor({ onAvatarState, onChat, onError, onConnectionChange }) {
            this.onAvatarState = onAvatarState;
            this.onChat = onChat;
            this.onError = onError;
            this.onConnectionChange = onConnectionChange || (() => {});
            this.socket = null;
            this._connect();
        }

        _url() {
            const scheme = location.protocol === "https:" ? "wss:" : "ws:";
            // Jeton optionnel (config.API_TOKEN côté serveur) : vide tant
            // que Cyril n'a rien configuré, voir ROADMAP.md §2. Lu depuis
            // localStorage plutôt que codé en dur, pour ne jamais committer
            // un jeton réel dans ce fichier.
            const token = window.localStorage.getItem("lucas_api_token") || "";
            const query = token ? `?token=${encodeURIComponent(token)}` : "";
            return `${scheme}//${location.host}/ws${query}`;
        }

        _connect() {
            this.socket = new WebSocket(this._url());

            this.socket.addEventListener("open", () => {
                this.onConnectionChange(true);
                this._send({ type: "hello", client: "lucas_pwa", version: "1.0" });
            });

            this.socket.addEventListener("message", (event) => {
                let data;
                try {
                    data = JSON.parse(event.data);
                } catch {
                    return;
                }
                this._dispatch(data);
            });

            this.socket.addEventListener("close", () => {
                this.onConnectionChange(false);
                setTimeout(() => this._connect(), RECONNECT_DELAY_MS);
            });

            this.socket.addEventListener("error", () => {
                // "close" suit toujours "error" sur un WebSocket — la
                // reconnexion est gérée là, pas ici, pour ne pas la
                // programmer deux fois.
            });
        }

        _dispatch(data) {
            switch (data.type) {
                case "avatar_state":
                    this.onAvatarState(data.state, data.text || "");
                    break;
                case "chat":
                    this.onChat(data.text || "", data.from_lucas !== false);
                    break;
                case "error":
                    this.onError(data.detail || "erreur inconnue");
                    break;
                case "system":
                    // Charge machine — pas affichée dans la PWA pour l'instant
                    // (écran mobile trop petit pour trois jauges de plus).
                    break;
                default:
                    break;
            }
        }

        _send(payload) {
            if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                this.socket.send(JSON.stringify(payload));
            }
        }

        sendChat(text) {
            this._send({ type: "chat", text });
        }

        sendAudio(audioBase64) {
            this._send({ type: "audio", audio_base64: audioBase64 });
        }

        sendImage(imageBase64, text) {
            const payload = { type: "image", image_base64: imageBase64 };
            if (text) payload.text = text;
            this._send(payload);
        }
    }

    window.Lucas.LucasSocket = LucasSocket;
})();
