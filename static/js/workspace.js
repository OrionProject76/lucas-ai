// static/js/workspace.js — Workspace Luca's (IDEAS.md #102, E-1).
//
// Page autonome, pas rattachée à app.js : ce tableau de bord n'a pas
// besoin du chat/WebSocket, seulement d'un jeton et d'un fetch vers
// /workspace/summary. Le bootstrap du jeton depuis l'URL est dupliqué
// (pas extrait en commun) plutôt qu'une dépendance croisée avec app.js,
// pour qu'un lien /app/workspace.html?token=... fonctionne seul, sans
// être passé d'abord par index.html.
//
// Glisser-déposer + tailles (09/08/2026) : Pointer Events plutôt que
// l'API HTML5 Drag & Drop — cette dernière n'a pas de support tactile
// fiable, alors que Pointer Events unifie souris/tactile/stylet dans un
// seul modèle, testé sur mobile ET PC (voir ROADMAP.md §5.77).

(function () {
    const CARD_IDS = ["reports", "requests", "actions", "objectives"];
    const CARD_SIZES = ["S", "M", "L", "XL"];

    function gridEl() {
        return document.getElementById("workspace-grid");
    }

    function cardEl(cardId) {
        return document.getElementById(`card-${cardId}`);
    }

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

    // ── Disposition (glisser-déposer + tailles) ─────────────────────────

    function applyCardSize(cardId, size) {
        const card = cardEl(cardId);
        if (!card) return;
        for (const s of CARD_SIZES) card.classList.remove(`card-size-${s}`);
        card.classList.add(`card-size-${size}`);
        for (const btn of card.querySelectorAll(".workspace-size-btn")) {
            btn.classList.toggle("active", btn.dataset.size === size);
        }
    }

    function applyLayout(layout) {
        const grid = gridEl();
        // appendChild sur un noeud déjà présent dans le document le
        // DÉPLACE (ne le duplique pas) — suffisant pour appliquer
        // n'importe quel ordre en une seule passe.
        for (const cardId of layout.order || []) {
            const card = cardEl(cardId);
            if (card) grid.appendChild(card);
        }
        for (const cardId of CARD_IDS) {
            applyCardSize(cardId, (layout.sizes && layout.sizes[cardId]) || "M");
        }
    }

    function currentLayout() {
        const grid = gridEl();
        const order = Array.from(grid.querySelectorAll(".workspace-card")).map(
            (card) => card.dataset.cardId
        );
        const sizes = {};
        for (const cardId of CARD_IDS) {
            const card = cardEl(cardId);
            sizes[cardId] = CARD_SIZES.find((s) => card.classList.contains(`card-size-${s}`)) || "M";
        }
        return { order, sizes };
    }

    let saveLayoutTimer = null;
    function saveLayoutDebounced() {
        // Un glisser peut survoler plusieurs cartes avant de se stabiliser
        // — n'enregistrer que l'état final, pas chaque étape intermédiaire.
        clearTimeout(saveLayoutTimer);
        saveLayoutTimer = setTimeout(() => {
            fetch("/workspace/layout", {
                method: "PUT",
                headers: { "Content-Type": "application/json", ...authHeaders() },
                body: JSON.stringify(currentLayout()),
            }).catch(() => {
                // Une disposition non enregistrée n'est pas critique : Cyril
                // la revoit à l'écran et peut la redéplacer, jamais une
                // erreur bloquante pour le reste de la page.
            });
        }, 250);
    }

    async function loadLayout() {
        try {
            const response = await fetch("/workspace/layout", { headers: authHeaders() });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            applyLayout(await response.json());
        } catch (error) {
            // Pas de disposition chargeable (jeton, réseau) : reste sur
            // l'ordre/tailles par défaut déjà présents dans le HTML.
        }
    }

    function initSizeControls() {
        for (const btn of document.querySelectorAll(".workspace-size-btn")) {
            btn.addEventListener("click", () => {
                const card = btn.closest(".workspace-card");
                applyCardSize(card.dataset.cardId, btn.dataset.size);
                saveLayoutDebounced();
            });
        }
    }

    // Une carte qui vient d'être glissée peut se retrouver, sous le
    // point de dépôt, à la place d'un AUTRE élément interactif (bouton de
    // taille d'une carte voisine) — la réorganisation en direct pendant
    // le drag déplace continuellement le contenu sous le doigt/curseur.
    // Un clic fantôme sur cet élément juste après un pointerup serait une
    // vraie régression (déclenché en conditions réelles, pas seulement en
    // test automatisé — même mécanisme qu'un tap qui "traverse" un
    // élément recomposé sous lui sur mobile). Un seul indicateur, purgé
    // par le tout premier clic qui suit un glisser, capture-phase pour
    // intercepter avant tout gestionnaire de clic spécifique (bouton de
    // taille, poignée...).
    let justDragged = false;
    document.addEventListener(
        "click",
        (event) => {
            if (!justDragged) return;
            justDragged = false;
            event.preventDefault();
            event.stopPropagation();
        },
        true
    );

    function initDragAndDrop() {
        const grid = gridEl();
        let dragCard = null;

        function cardCenter(card) {
            const rect = card.getBoundingClientRect();
            return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
        }

        // Distance euclidienne au centre de chaque autre carte, pas
        // seulement "au-dessus/en-dessous" — correct aussi bien en une
        // colonne (mobile, voir le media query de workspace.css) qu'en
        // plusieurs colonnes (desktop, flex-wrap).
        function closestSibling(clientX, clientY) {
            let closest = null;
            let closestDist = Infinity;
            for (const card of grid.querySelectorAll(".workspace-card")) {
                if (card === dragCard) continue;
                const center = cardCenter(card);
                const dist = (clientX - center.x) ** 2 + (clientY - center.y) ** 2;
                if (dist < closestDist) {
                    closestDist = dist;
                    closest = card;
                }
            }
            return closest;
        }

        function onPointerMove(event) {
            if (!dragCard) return;
            event.preventDefault();
            const target = closestSibling(event.clientX, event.clientY);
            if (!target) return;
            const children = Array.from(grid.children);
            if (children.indexOf(dragCard) < children.indexOf(target)) {
                grid.insertBefore(dragCard, target.nextSibling);
            } else {
                grid.insertBefore(dragCard, target);
            }
        }

        function endDrag() {
            if (!dragCard) return;
            dragCard.classList.remove("dragging");
            dragCard = null;
            justDragged = true;
            window.removeEventListener("pointermove", onPointerMove);
            window.removeEventListener("pointerup", endDrag);
            window.removeEventListener("pointercancel", endDrag);
            saveLayoutDebounced();
        }

        for (const handle of document.querySelectorAll(".workspace-drag-handle")) {
            handle.addEventListener("pointerdown", (event) => {
                event.preventDefault();
                dragCard = handle.closest(".workspace-card");
                dragCard.classList.add("dragging");
                window.addEventListener("pointermove", onPointerMove);
                window.addEventListener("pointerup", endDrag);
                window.addEventListener("pointercancel", endDrag);
            });

            // Équivalent clavier minimal (accessibilité) : flèches pour
            // déplacer la carte dans l'ordre, sans glisser-déposer complet
            // façon ARIA — suffisant pour rester opérable au clavier.
            handle.addEventListener("keydown", (event) => {
                if (!["ArrowUp", "ArrowLeft", "ArrowDown", "ArrowRight"].includes(event.key)) return;
                event.preventDefault();
                const card = handle.closest(".workspace-card");
                const cards = Array.from(grid.querySelectorAll(".workspace-card"));
                const index = cards.indexOf(card);
                const moveEarlier = event.key === "ArrowUp" || event.key === "ArrowLeft";
                if (moveEarlier && index > 0) {
                    grid.insertBefore(card, cards[index - 1]);
                } else if (!moveEarlier && index < cards.length - 1) {
                    grid.insertBefore(card, cards[index + 1].nextSibling);
                } else {
                    return;
                }
                handle.focus();
                saveLayoutDebounced();
            });
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        saveTokenFromUrl();
        initSizeControls();
        initDragAndDrop();
        document.getElementById("workspace-refresh").addEventListener("click", () => {
            loadLayout();
            loadSummary();
        });
        loadLayout();
        loadSummary();
    });
})();
