// static/js/app.js — assemble avatar, websocket, chat, micro et caméra.

(function () {
    document.addEventListener("DOMContentLoaded", () => {
        const avatar = new window.Lucas.Avatar(
            document.getElementById("avatar-canvas"),
            document.getElementById("avatar-label")
        );
        const chat = new window.Lucas.Chat(document.getElementById("chat-log"));
        const banner = document.getElementById("connection-banner");

        const socket = new window.Lucas.LucasSocket({
            onAvatarState: (state) => avatar.setState(state),
            onChat: (text, fromLucas) => {
                if (fromLucas) chat.addLucasMessage(text);
            },
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
            socket.sendChat(text);
            input.value = "";
        });

        new window.Lucas.MicRecorder(document.getElementById("mic-btn"), {
            onAudioReady: (audioBase64) => socket.sendAudio(audioBase64),
            onError: (message) => chat.addError(message),
        });

        new window.Lucas.CameraCapture(document.getElementById("camera-btn"), {
            onImageReady: (imageBase64) => socket.sendImage(imageBase64),
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
