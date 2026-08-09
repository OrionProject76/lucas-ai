// static/js/home.js — écran d'accueil mobile (F-1, cowork_workspace/BRIEF_ACCUEIL_MOBILE_F1.md)
//
// Vue par défaut à l'ouverture : orbe (avatar-panel, partagé avec le chat,
// jamais dupliqué) + liste compacte de ce que modules/workspace_manager.py
// expose déjà via /workspace/summary (même route que le Workspace PC,
// même jeton) + barre de navigation basse (Chat/Vision/Workspace/Réglages).
//
// Aucune nouvelle logique métier (brief §2) : Vision et Réglages ne font
// que déclencher les boutons déjà câblés ailleurs (camera-btn, chat,
// activity-toggle...) — voir _forwardClick() plus bas.
//
// Instancié depuis app.js (comme ActivityConsole/DocumentsPanel/...), pas
// un second DOMContentLoaded indépendant — un seul point d'assemblage
// pour toute la page, même discipline que le reste de ce fichier.

window.Lucas = window.Lucas || {};

(function () {
    function authHeaders() {
        const token = window.localStorage.getItem("lucas_api_token") || "";
        return token ? { Authorization: `Bearer ${token}` } : {};
    }

    function formatDate(isoString) {
        if (!isoString) return "";
        const date = new Date(isoString);
        if (Number.isNaN(date.getTime())) return isoString;
        return date.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });
    }

    // Un clic simulé sur un bouton déjà câblé ailleurs (documents.js,
    // finance.js, activity.js, security.js, voice_output.js, camera.js) —
    // jamais une seconde implémentation de la même ouverture/fermeture.
    //
    // ⚠️ setTimeout(0), pas un appel direct — bug réel trouvé en testant
    // "Réglages -> État de sécurité" (09/08/2026) : security.js ferme le
    // popover sur tout clic hors de son bouton/popover (document,
    // capture). Un forwardClick() synchrone déclenche security-badge.click()
    // PENDANT la remontée (bubbling) du clic d'origine sur #settings-security
    // — le popover s'ouvre, puis le clic d'origine continue sa remontée
    // jusqu'à `document`, dont la cible (#settings-security) est bien hors
    // du badge/popover : le gestionnaire "clic extérieur" le referme aussitôt,
    // dans le MÊME tour d'événement. Différer d'un tick laisse le clic
    // d'origine terminer sa remontée avant que le clic simulé n'existe.
    function forwardClick(id) {
        setTimeout(() => {
            const el = document.getElementById(id);
            if (el) el.click();
        }, 0);
    }

    function renderEmpty(container, message) {
        const empty = document.createElement("div");
        empty.className = "home-empty";
        empty.textContent = message;
        container.appendChild(empty);
    }

    function appendHomeLink(container, icon, titleText, metaText, href) {
        const item = document.createElement("a");
        item.className = "home-item";
        item.href = href;

        const iconEl = document.createElement("span");
        iconEl.className = "home-item-icon";
        iconEl.textContent = icon;
        item.appendChild(iconEl);

        const text = document.createElement("span");
        text.className = "home-item-text";
        const title = document.createElement("span");
        title.className = "home-item-title";
        title.textContent = titleText;
        text.appendChild(title);
        const meta = document.createElement("span");
        meta.className = "home-item-meta";
        meta.textContent = metaText;
        text.appendChild(meta);
        item.appendChild(text);

        container.appendChild(item);
    }

    function appendHomeAction(container, icon, titleText, metaText, onClick) {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "home-item home-item-action";

        const iconEl = document.createElement("span");
        iconEl.className = "home-item-icon";
        iconEl.textContent = icon;
        item.appendChild(iconEl);

        const text = document.createElement("span");
        text.className = "home-item-text";
        const title = document.createElement("span");
        title.className = "home-item-title";
        title.textContent = titleText;
        text.appendChild(title);
        const meta = document.createElement("span");
        meta.className = "home-item-meta";
        meta.textContent = metaText;
        text.appendChild(meta);
        item.appendChild(text);

        item.addEventListener("click", onClick);
        container.appendChild(item);
    }

    class Home {
        constructor() {
            this.homeView = document.getElementById("home-view");
            this.chatView = document.getElementById("chat-view");
            this.listEl = document.getElementById("home-list");
            this.avatarPanel = document.getElementById("avatar-panel");
            this.navChat = document.getElementById("nav-chat");
            this.textInput = document.getElementById("text-input");
            this.inputForm = document.getElementById("input-bar");

            this.avatarPanel.addEventListener("click", () => this.showHome());
            this.navChat.addEventListener("click", () => this.showChat());

            this._initVisionDrawer();
            this._initSettingsDrawer();

            this.load();
        }

        // ── Vues (accueil <-> chat) ──────────────────────────────────────

        showChat() {
            this.homeView.style.display = "none";
            this.chatView.style.display = "flex";
            this.navChat.classList.add("active");
        }

        showHome() {
            this.chatView.style.display = "none";
            this.homeView.style.display = "flex";
            this.navChat.classList.remove("active");
        }

        // Raccourci vision (brief §3.2/§3.3) : bascule sur le chat,
        // pré-remplit et envoie la question canonique ("regarde mon
        // écran" — même formulation que le cas nominal de
        // test_intent.py) — réutilise TOUT le pipeline existant (chat.js
        // -> websocket -> core/intent.py -> core/router.py ->
        // vision_manager). Aucune nouvelle route.
        captureScreen() {
            this.showChat();
            this.textInput.value = "Regarde mon écran";
            this.inputForm.requestSubmit();
        }

        // ── Liste compacte (brief §3.2) ──────────────────────────────────

        async load() {
            this.listEl.textContent = "";
            try {
                const response = await fetch("/workspace/summary", { headers: authHeaders() });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const summary = await response.json();
                this._render(summary);
            } catch (error) {
                renderEmpty(
                    this.listEl,
                    "Aperçu indisponible (connexion ou jeton invalide) — le chat reste utilisable."
                );
                this._appendVisionShortcut();
            }
        }

        _render(summary) {
            let hasItem = false;

            const latestReport = (summary.reports || [])[0];
            if (latestReport) {
                hasItem = true;
                appendHomeLink(
                    this.listEl, "📄", latestReport.title,
                    `${latestReport.filename} · ${formatDate(latestReport.modified_at)}`,
                    "/app/workspace.html"
                );
            }

            const latestRequest = (summary.pending_requests || [])[0];
            if (latestRequest) {
                hasItem = true;
                appendHomeLink(
                    this.listEl, "📝", latestRequest.title,
                    `Demande en attente · ${formatDate(latestRequest.modified_at)}`,
                    "/app/workspace.html"
                );
            }

            if (!hasItem) {
                renderEmpty(this.listEl, "Rien de nouveau côté rapports ou demandes.");
            }

            this._appendVisionShortcut();
        }

        _appendVisionShortcut() {
            appendHomeAction(
                this.listEl, "🖥️", "Capture d'écran", "Raccourci direct — mode vision",
                () => this.captureScreen()
            );
        }

        // ── Tiroir Vision (brief §3.3) ────────────────────────────────────

        _initVisionDrawer() {
            const drawer = document.getElementById("vision-drawer");
            document.getElementById("nav-vision").addEventListener("click", () => {
                drawer.classList.add("open");
            });
            document.getElementById("vision-close").addEventListener("click", () => {
                drawer.classList.remove("open");
            });
            document.getElementById("vision-screen").addEventListener("click", () => {
                drawer.classList.remove("open");
                this.captureScreen();
            });
            document.getElementById("vision-camera").addEventListener("click", () => {
                drawer.classList.remove("open");
                this.showChat();
                forwardClick("camera-btn");
            });
        }

        // ── Tiroir Réglages (brief §3.3) — consolide des panneaux existants ──

        _initSettingsDrawer() {
            const drawer = document.getElementById("settings-drawer");
            document.getElementById("nav-settings").addEventListener("click", () => {
                drawer.classList.add("open");
            });
            document.getElementById("settings-close").addEventListener("click", () => {
                drawer.classList.remove("open");
            });
            const forwards = {
                "settings-voice": "speak-toggle",
                "settings-security": "security-badge",
                "settings-documents": "documents-toggle",
                "settings-finance": "finance-toggle",
                "settings-activity": "activity-toggle",
            };
            for (const [settingsId, targetId] of Object.entries(forwards)) {
                document.getElementById(settingsId).addEventListener("click", () => {
                    drawer.classList.remove("open");
                    forwardClick(targetId);
                });
            }
        }
    }

    window.Lucas.Home = Home;
})();
