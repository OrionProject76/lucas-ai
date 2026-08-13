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
                // ⚠️ Annonce du mode capteur ICI, pas au constructeur de
                // PcSensor (corrigé le 13/08/2026, ROADMAP.md §5.97).
                // pc_sensor.js appelait _announce() depuis son
                // constructeur, exécuté dans le MÊME tick synchrone que
                // `new LucasSocket()` : le socket était encore en
                // CONNECTING, et _send() n'envoie que sur OPEN. L'annonce
                // partait donc dans le vide à CHAQUE ouverture de la PWA —
                // mesuré, 0 message émis. Comme le toggle est persistant,
                // Cyril ne le rebasculait jamais, et l'indicateur du PC ne
                // s'allumait jamais.
                //
                // Ici, c'est aussi ce qui réannonce l'état après une
                // reconnexion — le cas du téléphone qui perd le réseau.
                const sensor = window.Lucas.pcSensor;
                if (sensor && sensor.isActive()) {
                    this.sendPcSensorMode(true);
                }
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
            this._tagPcSensor(payload);
            this._send(payload);
        }

        sendImage(imageBase64, text, speak) {
            const payload = { type: "image", image_base64: imageBase64 };
            if (text) payload.text = text;
            if (speak) payload.speak = true;
            this._tagPcSensor(payload);
            this._send(payload);
        }

        // Posé ici plutôt que dans chaque appelant : audio.js, camera.js
        // et conversation_mode.js envoient tous par ces deux méthodes, et
        // aucun d'eux n'a à connaître le mode capteur. Volontairement
        // ABSENT de sendChat() — le pont transporte les capteurs, pas le
        // clavier (décision du 12/08, voir pc_sensor.js).
        _tagPcSensor(payload) {
            const sensor = window.Lucas.pcSensor;
            if (sensor && sensor.isActive()) {
                payload.pc_sensor = true;
                payload.tts_target = sensor.ttsTarget();
                // ⚠️ CORRECTIF TEMPORAIRE du 13/08/2026 (ROADMAP.md §5.96).
                // Le mode conversation impose la voix sur le téléphone,
                // même si Cyril a choisi « Voix sur : PC ».
                //
                // Pourquoi : le tour-à-tour de conversation_mode.js repose
                // sur notifyPlaybackEnded(), déclenché par la fin de
                // lecture de l'audio SUR CE TÉLÉPHONE. Sortie sur PC = le
                // serveur n'envoie aucun `speech` ici (api/server.py,
                // `if speak_wanted and not speak_on_pc`), donc ce signal
                // n'arrive jamais et il ne reste que la grâce de 6 s —
                // écrite pour le cas « pas de voix du tout ». Mesuré : une
                // réponse de 240 caractères fait parler le PC 12,7 s, le
                // micro se rouvre 6,7 s trop tôt, et le VAD réentend
                // Luca's parler.
                //
                // Le relais du TEXTE vers le PC n'est PAS touché :
                // `pc_sensor` reste posé, la session PC continue de tout
                // recevoir. Seule la voix reste ici, le temps que le vrai
                // correctif (signal de fin de lecture PC → serveur →
                // téléphone) soit construit.
                if (payload.conversation_mode) {
                    payload.tts_target = "phone";
                }
            }
        }

        // Bascule du mode côté téléphone — sert l'indicateur du desktop.
        // N'est jamais une question : le serveur la traite avant tout
        // traitement de conversation (api/server.py).
        sendPcSensorMode(active) {
            this._send({ type: "pc_sensor_mode", active: !!active });
        }
    }

    window.Lucas.LucasSocket = LucasSocket;
})();
