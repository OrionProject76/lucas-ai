// static/sw.js — cache l'app shell seulement, jamais le trafic API/WS.
//
// Le WebSocket n'est de toute façon pas interceptable par fetch. Les
// requêtes REST (aucune utilisée par ce client aujourd'hui, tout passe
// par /ws) ne doivent JAMAIS être servies depuis le cache si elles
// apparaissent un jour — une réponse de LucasCore périmée serait pire
// qu'une absence de réponse.

// v4 (02/08/2026) : ajout de voice_output.js (réponses vocales, pont
// mobile TTS). Le nom change à chaque fois pour forcer un install()
// frais — sans ça, un téléphone avec la PWA déjà installée garderait
// indéfiniment l'ancien app shell en cache et ne verrait jamais le
// nouveau fichier.
const CACHE_NAME = "lucas-shell-v4";
const SHELL_FILES = [
    "/app/",
    "/app/index.html",
    "/app/manifest.json",
    "/app/css/style.css",
    "/app/js/avatar.js",
    "/app/js/websocket.js",
    "/app/js/chat.js",
    "/app/js/activity.js",
    "/app/js/security.js",
    "/app/js/voice_output.js",
    "/app/js/audio.js",
    "/app/js/camera.js",
    "/app/js/app.js",
    "/app/icons/icon-192.png",
    "/app/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES))
    );
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    const url = new URL(event.request.url);
    // Uniquement l'app shell, jamais /ws ni un futur appel REST.
    if (!url.pathname.startsWith("/app/")) return;

    event.respondWith(
        caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
});
