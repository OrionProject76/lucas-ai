// static/sw.js — cache l'app shell seulement, jamais le trafic API/WS.
//
// Le WebSocket n'est de toute façon pas interceptable par fetch. Les
// requêtes REST (aucune utilisée par ce client aujourd'hui, tout passe
// par /ws) ne doivent JAMAIS être servies depuis le cache si elles
// apparaissent un jour — une réponse de LucasCore périmée serait pire
// qu'une absence de réponse.

// v6 (02/08/2026) : correctif camera.js — la caméra s'éteignait seule
// presque aussitôt après activation, sans erreur ni photo (même famille
// de bug que l'audio en v5 : élément média jamais attaché au DOM). Le
// nom change à chaque fois pour forcer un install() frais — sans ça, un
// téléphone avec la PWA déjà installée garderait indéfiniment l'ancien
// fichier buggé en cache.
// v9 (05/08/2026) : correctif audio.js — flux micro mis en cache et
// réutilisé entre enregistrements (perte de la première syllabe d'une
// phrase, cause probable identifiée en conditions réelles avec Cyril,
// voir ROADMAP.md §5.28). Même raison que v6 : sans bump, le téléphone
// garderait l'ancien audio.js en cache malgré le fichier serveur à jour.
// v10 (05/08/2026) : websocket.js transporte le jeton dans l'en-tête
// Sec-WebSocket-Protocol au lieu de la query string, pour qu'il cesse
// d'être journalisé en clair (ROADMAP.md §5.29). Bump indispensable ici :
// sans lui, le téléphone continuerait d'envoyer `?token=` depuis son
// cache, et le correctif ne changerait rien pour le seul client réel.
// v11 (05/08/2026) : trois correctifs client remontés par Cyril en usage
// réel — réactivation du son en cours de lecture (voice_output.js),
// barge-in désactivé le temps d'être calibré (il coupait Luca's au milieu
// de ses phrases), autoGainControl explicite pour le micro (audio.js).
// Voir ROADMAP.md §5.31.
// v12 (08/08/2026) : bump OUBLIÉ lors de l'ajout du bouton Workspace
// (index.html + style.css modifiés le même jour, Brique Workspace E-1,
// ROADMAP.md §5.73) — sans lui, un client avec le Service Worker déjà
// installé garde indéfiniment l'ancien index.html/style.css en cache
// (mécanisme documenté juste au-dessus : "le nom change à chaque fois
// pour forcer un install() frais"). Cause la plus probable des deux bugs
// remontés par Cyril le 08/08/2026 (bouton Workspace mal rendu, message
// de connexion dupliqué) — voir ROADMAP.md §5.74 pour le détail complet.
const CACHE_NAME = "lucas-shell-v12";
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
