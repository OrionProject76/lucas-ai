// static/js/documents.js — panneau "Mes documents" (contrepartie mobile
// de modules/semantic_desktop.py, IDEAS.md #16, construit le 03/08/2026).
//
// Lecture seule côté serveur (voir semantic_desktop.py, garde-fou testé
// contre toute écriture fichier) : ce panneau ne fait qu'afficher ce que
// /documents, /documents/periods et /documents/{id}/related renvoient,
// jamais une action sur un fichier. Même token que /history (voir
// api/server.py) — les noms de fichiers de Cyril sont aussi révélateurs
// que l'historique de conversation.
//
// Chargé à la demande (à l'ouverture du tiroir), pas au démarrage de la
// PWA : un téléphone avec une connexion instable ne doit pas bloquer le
// chat pour une fonctionnalité annexe.

window.Lucas = window.Lucas || {};

(function () {
    function authHeaders() {
        const token = window.localStorage.getItem("lucas_api_token") || "";
        return token ? { Authorization: `Bearer ${token}` } : {};
    }

    class DocumentsPanel {
        constructor({ toggleEl, drawerEl, closeEl, logEl }) {
            this.drawerEl = drawerEl;
            this.logEl = logEl;
            this._open = false;
            this._loaded = false;

            toggleEl.addEventListener("click", () => this.toggle());
            closeEl.addEventListener("click", () => this.close());
        }

        toggle() {
            if (this._open) this.close();
            else this.open();
        }

        open() {
            this._open = true;
            this.drawerEl.classList.add("open");
            // Chargé une seule fois par session PWA — Cyril peut rouvrir/
            // refermer le tiroir librement sans relancer un appel réseau à
            // chaque fois. La base ne change pas pendant qu'il discute.
            if (!this._loaded) this._load();
        }

        close() {
            this._open = false;
            this.drawerEl.classList.remove("open");
        }

        async _load() {
            this.logEl.textContent = "Chargement...";
            try {
                const response = await fetch("/documents/periods", { headers: authHeaders() });
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                const { periods } = await response.json();
                this._loaded = true;
                this._render(periods);
            } catch (error) {
                this.logEl.textContent =
                    "Impossible de charger les documents (connexion ou jeton invalide).";
            }
        }

        _render(periods) {
            this.logEl.textContent = "";

            // Plus récent d'abord — "sans période" toujours en dernier,
            // ce n'est pas une année à trier parmi les autres.
            const years = Object.keys(periods)
                .filter((key) => key !== "sans période")
                .sort((a, b) => b.localeCompare(a));
            if (periods["sans période"]) years.push("sans période");

            if (years.length === 0) {
                this.logEl.textContent = "Aucun document indexé.";
                return;
            }

            for (const year of years) {
                const group = document.createElement("details");
                group.className = "documents-group";

                const summary = document.createElement("summary");
                summary.textContent = `${year} (${periods[year].length})`;
                group.appendChild(summary);

                for (const name of periods[year]) {
                    group.appendChild(this._documentRow(name));
                }

                this.logEl.appendChild(group);
            }
        }

        _documentRow(name) {
            const row = document.createElement("div");
            row.className = "document-row";

            const label = document.createElement("button");
            label.type = "button";
            label.className = "document-name";
            label.textContent = name;

            const related = document.createElement("div");
            related.className = "document-related";
            related.hidden = true;

            label.addEventListener("click", () => this._toggleRelated(name, related));

            row.append(label, related);
            return row;
        }

        async _toggleRelated(name, container) {
            if (!container.hidden) {
                container.hidden = true;
                return;
            }
            if (container.dataset.loaded) {
                container.hidden = false;
                return;
            }

            container.hidden = false;
            container.textContent = "Recherche de documents proches...";
            try {
                const response = await fetch(
                    `/documents/${encodeURIComponent(name)}/related`,
                    { headers: authHeaders() }
                );
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const { related } = await response.json();
                container.textContent = "";
                if (related.length === 0) {
                    container.textContent = "Aucun document proche trouvé.";
                } else {
                    for (const otherName of related) {
                        const line = document.createElement("div");
                        line.textContent = `↳ ${otherName}`;
                        container.appendChild(line);
                    }
                }
                container.dataset.loaded = "1";
            } catch (error) {
                container.textContent = "Recherche indisponible.";
            }
        }
    }

    window.Lucas.DocumentsPanel = DocumentsPanel;
})();
