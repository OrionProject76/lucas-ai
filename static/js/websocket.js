// static/js/websocket.js — connexion unique vers /ws, protocole api/protocol.py.
//
// Même rôle que Lucas3D/scripts/websocket_client.gd côté Godot : un seul
// canal, un vocabulaire partagé (avatar_state / chat / system / error),
// jamais un protocole parallèle pour la PWA.

window.Lucas = window.Lucas || {};

(function () {
    const RECONNECT_DELAY_MS = 3000;

    // Doivent rester identiques à WS_SUBPROTOCOL / WS_TOKEN_SUBPROTOCOL_PREFIX
    // dans api/server.py.
    const SUBPROTOCOL = "lucas.v1";
    const TOKEN_SUBPROTOCOL_PREFIX = "lucas-token.";

    // Caractères autorisés dans un sous-protocole WebSocket (« token » HTTP,
    // RFC 7230). Un jeton produit par secrets.token_urlsafe les respecte
    // toujours ; un jeton écrit à la main avec un « : » ou un espace, non —
    // et le navigateur refuserait alors de construire le WebSocket.
    const HTTP_TOKEN_CHARS = /^[A-Za-z0-9!#$%&'*+\-.^_`|~]+$/;

    class LucasSocket {
        constructor({
            onAvatarState,
            onChat,
            onActivity,
            onSecurityStatus,
            onSpeech,
            onVoiceCommand,
            onError,
            onConnectionChange,
        }) {
            this.onAvatarState = onAvatarState;
            this.onChat = onChat;
            this.onActivity = onActivity || (() => {});
            this.onSecurityStatus = onSecurityStatus || (() => {});
            this.onSpeech = onSpeech || (() => {});
            // Commande vocale d'arrêt du mode conversation (api/protocol.py,
            // voice_command()) — distincte de "speech" (réponse SYNTHÉTISÉE) :
            // ce message ne transporte jamais d'audio, juste une action.
            this.onVoiceCommand = onVoiceCommand || (() => {});
            this.onError = onError;
            this.onConnectionChange = onConnectionChange || (() => {});
            this.socket = null;
            this._connect();
        }

        // Jeton optionnel (config.API_TOKEN côté serveur) : vide tant que
        // Cyril n'a rien configuré, voir ROADMAP.md §2. Lu depuis
        // localStorage plutôt que codé en dur, pour ne jamais committer un
        // jeton réel dans ce fichier.
        _token() {
            return window.localStorage.getItem("lucas_api_token") || "";
        }

        // Le jeton voyage dans les sous-protocoles, donc dans l'en-tête
        // Sec-WebSocket-Protocol — jamais dans l'URL. Uvicorn journalise la
        // ligne de requête (query string comprise) mais pas les en-têtes :
        // c'est ce qui empêche le jeton d'atterrir en clair dans
        // data/logs/server_startup.log. Voir api/log_scrub.py.
        _protocols() {
            const token = this._token();
            const protocols = [SUBPROTOCOL];
            if (token && HTTP_TOKEN_CHARS.test(token)) {
                protocols.push(TOKEN_SUBPROTOCOL_PREFIX + token);
            }
            return protocols;
        }

        _url() {
            const scheme = location.protocol === "https:" ? "wss:" : "ws:";
            // Repli : un jeton contenant un caractère interdit en
            // sous-protocole repart par la query string, sinon la connexion
            // serait impossible. Cas rare (jeton écrit à la main), mais
            // échouer silencieusement serait pire qu'une valeur masquée
            // dans les logs.
            const token = this._token();
            const parRequete = token && !HTTP_TOKEN_CHARS.test(token);
            const query = parRequete ? `?token=${encodeURIComponent(token)}` : "";
            return `${scheme}//${location.host}/ws${query}`;
        }

        _connect() {
            this.socket = new WebSocket(this._url(), this._protocols());

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
                case "activity":
                    this.onActivity(data.kind || "", data.text || "");
                    break;
                case "security_status":
                    this.onSecurityStatus({
                        active: !!data.active,
                        last_scan_at: data.last_scan_at || null,
                        findings_24h: data.findings_24h || 0,
                        latest_summary: data.latest_summary || null,
                    });
                    break;
                case "speech":
                    // Réponse vocale synthétisée — distinct du type ENTRANT
                    // "audio" (micro du téléphone, sendAudio() plus bas).
                    // Voir api/protocol.py, speech().
                    this.onSpeech(data.audio_base64 || "", data.mime || "");
                    break;
                case "voice_command":
                    this.onVoiceCommand(data.action || "");
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

        sendChat(text, speak) {
            const payload = { type: "chat", text };
            if (speak) payload.speak = true;
            this._send(payload);
        }

        sendAudio(audioBase64, speak, conversationMode) {
            const payload = { type: "audio", audio_base64: audioBase64 };
            if (speak) payload.speak = true;
            // Seul ce drapeau active la détection de commande vocale
            // d'arrêt côté serveur (api/protocol.py, read_conversation_mode_flag) —
            // absent pour le micro push-to-talk classique (audio.js),
            // où dire "stop" doit rester un message normal.
            if (conversationMode) payload.conversation_mode = true;
            this._send(payload);
        }

        sendImage(imageBase64, text, speak) {
            const payload = { type: "image", image_base64: imageBase64 };
            if (text) payload.text = text;
            if (speak) payload.speak = true;
            this._send(payload);
        }
    }

    window.Lucas.LucasSocket = LucasSocket;
})();
