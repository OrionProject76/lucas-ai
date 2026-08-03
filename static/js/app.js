// static/js/app.js — assemble avatar, websocket, chat, micro et caméra.

(function () {
    // Jeton passé une seule fois par lien (?token=...), pour configurer le
    // téléphone sans écran de réglages à construire. Sauvegardé puis retiré
    // de l'URL tout de suite : un jeton ne doit pas traîner dans l'historique
    // ou les favoris du navigateur.
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
        const voiceOutput = new window.Lucas.VoiceOutput({
            toggleEl: document.getElementById("speak-toggle"),
            onBargeIn: () => activity.add("voice", "Interruption détectée — coupée immédiatement."),
        });

        const socket = new window.Lucas.LucasSocket({
            onAvatarState: (state) => avatar.setState(state),
            onChat: (text, fromLucas) => {
                if (fromLucas) chat.addLucasMessage(text);
            },
            onActivity: (kind, text) => activity.add(kind, text),
            onSecurityStatus: (status) => security.update(status),
            onSpeech: (audioBase64, mime) => voiceOutput.play(audioBase64, mime),
            onError: (detail) => chat.addError(detail),
            onConnectionChange: (connected) => {
                banner.classList.toggle("visible", !connected);
                banner.textContent = connected ? "" : "Reconnexion à Luca's...";
            },
        });

        const form = document.getElementById("input-bar");
        const input = document.getElementById("text-input");
        form.addEventListener("submit", (event) => {
            event.preventDefault();
            const text = input.value.trim();
            if (!text) return;
            chat.addUserMessage(text);
            socket.sendChat(text, voiceOutput.enabled);
            input.value = "";
        });

        new window.Lucas.MicRecorder(document.getElementById("mic-btn"), {
            onAudioReady: (audioBase64) => socket.sendAudio(audioBase64, voiceOutput.enabled),
            onError: (message) => chat.addError(message),
        });

        new window.Lucas.CameraCapture(document.getElementById("camera-btn"), {
            onImageReady: (imageBase64) =>
                socket.sendImage(imageBase64, undefined, voiceOutput.enabled),
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
