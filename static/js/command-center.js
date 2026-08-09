// static/js/command-center.js — Poste de Commandement IA (E-5).
//
// Page autonome, comme workspace.js : ni chat ni WebSocket, seulement un
// jeton et un fetch vers /capabilities (modules/capability_registry.py).
// Lecture seule stricte (brief §4) : aucun bouton d'action, seulement de
// la consultation.

(function () {
    const STATUS_CLASS = {
        "actif": "actif",
        "inactif": "inactif",
        "manuel": "manuel",
        "construit, non branché": "construit-non-branche",
    };

    function saveTokenFromUrl() {
        const params = new URLSearchParams(location.search);
        const token = params.get("token");
        if (!token) return;
        window.localStorage.setItem("lucas_api_token", token);
        params.delete("token");
        const clean = location.pathname + (params.toString() ? `?${params}` : "");
        history.replaceState(null, "", clean);
    }

    function authHeaders() {
        const token = window.localStorage.getItem("lucas_api_token") || "";
        return token ? { Authorization: `Bearer ${token}` } : {};
    }

    // createElement/textContent partout — noms/descriptions viennent du
    // code (modules/capability_registry.py), jamais traités comme du HTML
    // (même discipline que workspace.js).
    function appendCapability(container, capability) {
        const item = document.createElement("div");
        item.className = "workspace-item";

        const header = document.createElement("div");
        header.className = "command-center-item-header";

        const title = document.createElement("span");
        title.className = "workspace-item-title";
        title.textContent = capability.name;
        header.appendChild(title);

        const badge = document.createElement("span");
        const statusClass = STATUS_CLASS[capability.status] || "inactif";
        badge.className = `command-center-status-badge status-${statusClass}`;
        badge.textContent = capability.status;
        header.appendChild(badge);

        item.appendChild(header);

        const description = document.createElement("div");
        description.className = "workspace-item-meta";
        description.textContent = capability.description;
        item.appendChild(description);

        if (capability.detail) {
            const detail = document.createElement("div");
            detail.className = "command-center-item-detail";
            detail.textContent = capability.detail;
            item.appendChild(detail);
        }

        container.appendChild(item);
    }

    function renderCategories(container, capabilities) {
        container.textContent = "";
        const byCategory = new Map();
        for (const capability of capabilities) {
            if (!byCategory.has(capability.category)) byCategory.set(capability.category, []);
            byCategory.get(capability.category).push(capability);
        }

        for (const [category, items] of byCategory) {
            const section = document.createElement("section");
            section.className = "command-center-category";

            const heading = document.createElement("h2");
            heading.className = "command-center-category-heading";
            heading.textContent = category;
            section.appendChild(heading);

            const list = document.createElement("div");
            list.className = "command-center-list";
            for (const capability of items) appendCapability(list, capability);
            section.appendChild(list);

            container.appendChild(section);
        }
    }

    async function loadCapabilities() {
        const statusEl = document.getElementById("command-center-status");
        statusEl.textContent = "Chargement...";
        const categoriesEl = document.getElementById("command-center-categories");

        try {
            const response = await fetch("/capabilities", { headers: authHeaders() });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();

            document.getElementById("command-center-verified-at").textContent = data.verified_at;
            renderCategories(categoriesEl, data.capabilities);

            statusEl.textContent = `Actualisé à ${new Date().toLocaleTimeString("fr-FR")}`;
        } catch (error) {
            statusEl.textContent = "";
            categoriesEl.textContent = "";
            const err = document.createElement("div");
            err.className = "workspace-error";
            err.textContent = "Impossible de charger le registre (connexion ou jeton invalide).";
            categoriesEl.appendChild(err);
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        saveTokenFromUrl();
        document.getElementById("command-center-refresh").addEventListener("click", loadCapabilities);
        loadCapabilities();
    });
})();
