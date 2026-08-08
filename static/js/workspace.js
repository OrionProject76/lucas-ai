// static/js/workspace.js — Workspace Luca's (IDEAS.md #102, E-1).
//
// Page autonome, pas rattachée à app.js : ce tableau de bord n'a pas
// besoin du chat/WebSocket, seulement d'un jeton et d'un fetch vers
// /workspace/summary. Le bootstrap du jeton depuis l'URL est dupliqué
// (pas extrait en commun) plutôt qu'une dépendance croisée avec app.js,
// pour qu'un lien /app/workspace.html?token=... fonctionne seul, sans
// être passé d'abord par index.html.

(function () {
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

    function formatDate(isoString) {
        if (!isoString) return "";
        const date = new Date(isoString);
        if (Number.isNaN(date.getTime())) return isoString;
        return date.toLocaleString("fr-FR", {
            day: "2-digit", month: "2-digit", year: "numeric",
            hour: "2-digit", minute: "2-digit",
        });
    }

    function formatBytes(bytes) {
        if (bytes < 1024) return `${bytes} o`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
    }

    function renderEmpty(container, message) {
        const empty = document.createElement("div");
        empty.className = "workspace-empty";
        empty.textContent = message;
        container.appendChild(empty);
    }

    // Construit chaque ligne via createElement/textContent, jamais
    // innerHTML sur une valeur dynamique — titres de rapports, contenu
    // d'objectifs ou params d'action viennent de fichiers/DB, pas d'une
    // source figée : les traiter comme du texte, pas du HTML, coupe court
    // à toute injection (CLAUDE.md, éviter OWASP top 10).
    function appendItem(container, titleText, metaText, extraClass) {
        const item = document.createElement("div");
        item.className = extraClass ? `workspace-item ${extraClass}` : "workspace-item";

        const title = document.createElement("div");
        title.className = "workspace-item-title";
        title.textContent = titleText;
        item.appendChild(title);

        const meta = document.createElement("div");
        meta.className = "workspace-item-meta";
        meta.textContent = metaText;
        item.appendChild(meta);

        container.appendChild(item);
    }

    function renderFileList(container, entries, emptyMessage) {
        container.textContent = "";
        if (!entries || entries.length === 0) {
            renderEmpty(container, emptyMessage);
            return;
        }
        for (const entry of entries) {
            appendItem(
                container,
                entry.title,
                `${entry.filename} · ${formatBytes(entry.size_bytes)} · ${formatDate(entry.modified_at)}`
            );
        }
    }

    function renderActions(container, actions) {
        container.textContent = "";
        if (!actions || actions.length === 0) {
            renderEmpty(container, "Aucune action journalisée pour l'instant.");
            return;
        }
        for (const action of actions) {
            const params = action.params ? JSON.stringify(action.params) : "";
            appendItem(
                container,
                `${action.action} — ${action.result}`,
                `${action.source} · ${formatDate(action.created_at)}${params ? ` · ${params}` : ""}`,
                action.result === "denied" ? "denied" : ""
            );
        }
    }

    function renderObjectives(container, objectives) {
        container.textContent = "";
        if (!objectives || objectives.length === 0) {
            renderEmpty(container, "Aucun objectif prospectif enregistré pour l'instant.");
            return;
        }
        for (const objective of objectives) {
            appendItem(
                container,
                objective.content,
                `confiance ${(objective.confidence * 100).toFixed(0)} % · ` +
                    `importance ${(objective.importance * 100).toFixed(0)} % · ` +
                    formatDate(objective.date || objective.created_at)
            );
        }
    }

    async function loadSummary() {
        const statusEl = document.getElementById("workspace-status");
        statusEl.textContent = "Chargement...";

        try {
            const response = await fetch("/workspace/summary", { headers: authHeaders() });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const summary = await response.json();

            renderFileList(
                document.getElementById("reports-list"),
                summary.reports,
                "Aucun rapport pour l'instant."
            );
            renderFileList(
                document.getElementById("requests-list"),
                summary.pending_requests,
                "Aucune demande en attente."
            );
            renderActions(document.getElementById("actions-list"), summary.recent_actions);
            renderObjectives(document.getElementById("objectives-list"), summary.objectives);

            statusEl.textContent = `Actualisé à ${new Date().toLocaleTimeString("fr-FR")}`;
        } catch (error) {
            statusEl.textContent = "";
            for (const id of ["reports-list", "requests-list", "actions-list", "objectives-list"]) {
                const container = document.getElementById(id);
                container.textContent = "";
                const err = document.createElement("div");
                err.className = "workspace-error";
                err.textContent = "Impossible de charger le Workspace (connexion ou jeton invalide).";
                container.appendChild(err);
            }
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        saveTokenFromUrl();
        document.getElementById("workspace-refresh").addEventListener("click", loadSummary);
        loadSummary();
    });
})();
