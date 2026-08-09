// static/js/app.js — assemble avatar, websocket, chat, micro et caméra.

(function () {
    // Jeton passé une seule fois par lien (?token=...), pour configurer le
    // téléphone sans écran de réglages à construire. Sauvegardé puis retiré
    // de l'URL tout de suite.
    //
    // ⚠️ Ce que replaceState fait, et surtout ce qu'il NE fait PAS
    // (précisé le 05/08/2026 — la formulation d'origine, « un jeton ne doit
    // pas traîner dans l'historique », laissait croire le problème réglé).
    //
    // Il fait : retirer le jeton de la barre d'adresse, de l'entrée
    // d'historique de session, et donc de tout partage ou favori créé
    // ensuite. C'est réel et utile.
    //
    // Il ne fait pas : effacer l'URL d'ORIGINE de la base d'historique du
    // navigateur. Chrome enregistre la navigation avant que ce code ne
    // s'exécute ; aucun JavaScript ne peut revenir dessus. Le jeton reste
    // donc retrouvable dans l'historique de Chrome sur le téléphone,
    // jusqu'à ce que Cyril l'efface lui-même.
    //
    // Fermer ce trou pour de bon demande de changer la MÉTHODE
    // d'appairage (code à usage unique échangé contre le jeton, ou saisie
    // manuelle) — c'est-à-dire toucher à l'authentification. Trois options
    // sont décrites dans ROADMAP.md §5.33 ; la décision revient à Cyril,
    // elle n'est pas prise ici.
    function _saveTokenFromUrl() {
        const params = new URLSearchParams(location.search);
        const token = params.get("token");
        if (!token) return;
        window.localStorage.setItem("lucas_api_token", token);
        params.delete("token");
        const clean = location.pathname + (params.toString() ? `?${params}` : "");
        history.replaceState(null, "", clean);
    }

    document.addEventListener("DOMContentLoaded", () => {
        _saveTokenFromUrl();

        const avatar = new window.Lucas.Avatar(
            document.getElementById("avatar-canvas"),
            document.getElementById("avatar-label")
        );
        const chat = new window.Lucas.Chat(document.getElementById("chat-log"));
        const banner = document.getElementById("connection-banner");
        const activity = new window.Lucas.ActivityConsole({
            toggleEl: document.getElementById("activity-toggle"),
            drawerEl: document.getElementById("activity-drawer"),
            closeEl: document.getElementById("activity-close"),
            logEl: document.getElementById("activity-log"),
            badgeEl: document.getElementById("activity-badge"),
        });
        const security = new window.Lucas.SecurityBadge({
            badgeEl: document.getElementById("security-badge"),
            dotEl: document.getElementById("security-dot"),
            popoverEl: document.getElementById("security-popover"),
            textEl: document.getElementById("security-popover-text"),
        });
        new window.Lucas.DocumentsPanel({
            toggleEl: document.getElementById("documents-toggle"),
            drawerEl: document.getElementById("documents-drawer"),
            closeEl: document.getElementById("documents-close"),
            logEl: document.getElementById("documents-log"),
        });
        new window.Lucas.FinancePanel({
            toggleEl: document.getElementById("finance-toggle"),
            drawerEl: document.getElementById("finance-drawer"),
            closeEl: document.getElementById("finance-close"),
            logEl: document.getElementById("finance-log"),
        });
        new window.Lucas.Home();
        // Rempli après la création de ConversationMode (référence circulaire
        // socket <-> conversationMode) — voir plus bas.
        let conversationMode = null;
        const voiceOutput = new window.Lucas.VoiceOutput({
            toggleEl: document.getElementById("speak-toggle"),
            onBargeIn: () => activity.add("voice", "Interruption détectée — coupée immédiatement."),
            onPlaybackEnded: () => {
                if (conversationMode) conversationMode.notifyPlaybackEnded();
            },
        });

        const socket = new window.Lucas.LucasSocket({
            onAvatarState: (state) => {
                // Mode conversation actif : le serveur envoie "idle" en fin
                // de tour raté (transcription peu fiable, api/server.py) —
                // ce message arrive APRÈS "error", donc APRÈS que
                // conversationMode.notifyError() ait déjà remis l'avatar en
                // "écoute". Sans ce filtre, "idle" écrase "écoute" une
                // fraction de seconde plus tard, alors que le micro écoute
                // réellement encore — affichage trompeur, pas un problème
                // fonctionnel. Le mode ne connaît pas d'état "idle" tant
                // qu'il est actif : il redevient lui-même "écoute" via
                // notifyLucasReplied()/notifyPlaybackEnded()/notifyError().
                if (state === "idle" && conversationMode && conversationMode.active) return;
                avatar.setState(state);
            },
            onChat: (text, fromLucas) => {
                if (fromLucas) {
                    chat.addLucasMessage(text);
                    if (conversationMode) conversationMode.notifyLucasReplied();
                }
            },
            onActivity: (kind, text) => activity.add(kind, text),
            onSecurityStatus: (status) => security.update(status),
            onSpeech: (audioBase64, mime) => voiceOutput.play(audioBase64, mime),
            onError: (detail) => {
                chat.addError(detail);
                if (conversationMode) conversationMode.notifyError();
            },
            onConnectionChange: (connected) => {
                banner.classList.toggle("visible", !connected);
                banner.textContent = connected ? "" : "Reconnexion à Luca's...";
            },
        });

        // Mode conversation mains libres (BRIEF_MODE_VOCAL_CONTINU_MOBILE.md).
        conversationMode = new window.Lucas.ConversationMode({
            toggleEl: document.getElementById("conv-mode-toggle"),
            avatar,
            socket,
            voiceOutput,
            micBtnEl: document.getElementById("mic-btn"),
            onNotice: (text) => chat.addSystemNotice(text),
            onError: (message) => chat.addError(message),
        });

        const form = document.getElementById("input-bar");
        const input = document.getElementById("text-input");
        form.addEventListener("submit", (event) => {
            event.preventDefault();
            const text = input.value.trim();
            if (!text) return;
            chat.addUserMessage(text);
            // L'audio éventuellement mis de côté appartenait à l'échange
            // précédent : réactiver le son après cette nouvelle question ne
            // doit pas rejouer l'ancienne réponse (voir voice_output.js).
            voiceOutput.forgetPending();
            socket.sendChat(text, voiceOutput.enabled);
            input.value = "";
        });

        new window.Lucas.MicRecorder(document.getElementById("mic-btn"), {
            onAudioReady: (audioBase64) => {
                voiceOutput.forgetPending();
                socket.sendAudio(audioBase64, voiceOutput.enabled);
            },
            onError: (message) => chat.addError(message),
        });

        new window.Lucas.CameraCapture(document.getElementById("camera-btn"), {
            onImageReady: (imageBase64) => {
                voiceOutput.forgetPending();
                socket.sendImage(imageBase64, undefined, voiceOutput.enabled);
            },
            onError: (message) => chat.addError(message),
        });

        if ("serviceWorker" in navigator) {
            navigator.serviceWorker.register("/app/sw.js").catch(() => {
                // Pas grave : la PWA reste utilisable en ligne sans le
                // service worker, juste sans installation/hors-ligne.
            });
        }
    });
})();
