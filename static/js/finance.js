// static/js/finance.js — panneau "Mes finances" (contrepartie mobile de
// modules/finance_manager.py, Phase 2, fermé le 03/08/2026).
//
// Lecture seule côté serveur : ce panneau affiche ce que
// /finance/summary renvoie, jamais une écriture. Même token que
// /history et /documents (api/server.py) — un solde ou une dépense
// nommée est une donnée ultra-sensible (CLAUDE.md règle 3).
//
// Chargé à la demande (à l'ouverture du tiroir), pas au démarrage —
// même raisonnement que documents.js.

window.Lucas = window.Lucas || {};

(function () {
    function authHeaders() {
        const token = window.localStorage.getItem("lucas_api_token") || "";
        return token ? { Authorization: `Bearer ${token}` } : {};
    }

    function formatEuros(amount) {
        return `${amount.toFixed(2)} €`;
    }

    class FinancePanel {
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
            // Chargé une seule fois par session PWA, comme le tiroir
            // documents — data/finance/ ne change pas pendant que Cyril
            // discute.
            if (!this._loaded) this._load();
        }

        close() {
            this._open = false;
            this.drawerEl.classList.remove("open");
        }

        async _load() {
            this.logEl.textContent = "Chargement...";
            try {
                const response = await fetch("/finance/summary", { headers: authHeaders() });
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                const summary = await response.json();
                this._loaded = true;
                this._render(summary);
            } catch (error) {
                this.logEl.textContent =
                    "Impossible de charger les finances (connexion ou jeton invalide).";
            }
        }

        _render(summary) {
            this.logEl.textContent = "";

            if (!summary.has_data) {
                const empty = document.createElement("div");
                empty.className = "finance-empty";
                empty.textContent =
                    "Aucune transaction importée. Dépose un export CSV de ton " +
                    "relevé bancaire dans data/finance/ pour voir un résumé ici.";
                this.logEl.appendChild(empty);
                this._renderSkipped(summary.skipped_files);
                return;
            }

            const overview = document.createElement("div");
            overview.className = "finance-overview";
            overview.innerHTML = `
                <div class="finance-period">Du ${summary.period.start} au ${summary.period.end}
                    (${summary.transaction_count} transaction(s))</div>
                <div class="finance-balance">Solde : ${formatEuros(summary.balance)}</div>
                <div class="finance-line">Revenus : ${formatEuros(summary.income)}</div>
                <div class="finance-line">Dépenses : ${formatEuros(summary.expenses)}</div>
            `;
            this.logEl.appendChild(overview);

            const categories = Object.entries(summary.expenses_by_category);
            if (categories.length > 0) {
                const heading = document.createElement("div");
                heading.className = "finance-subheading";
                heading.textContent = "Dépenses par catégorie";
                this.logEl.appendChild(heading);

                for (const [category, amount] of categories) {
                    const share = summary.expenses ? (amount / summary.expenses) * 100 : 0;
                    const row = document.createElement("div");
                    row.className = "finance-category-row";
                    row.textContent = `${category} : ${formatEuros(amount)} (${share.toFixed(0)} %)`;
                    this.logEl.appendChild(row);
                }
            }

            if (summary.uncategorized.length > 0) {
                const heading = document.createElement("div");
                heading.className = "finance-subheading";
                heading.textContent = `⚠️ ${summary.uncategorized.length} transaction(s) non catégorisée(s)`;
                this.logEl.appendChild(heading);

                for (const t of summary.uncategorized.slice(0, 5)) {
                    const row = document.createElement("div");
                    row.className = "finance-category-row";
                    row.textContent = `${t.date} — ${t.libelle}`;
                    this.logEl.appendChild(row);
                }
            }

            this._renderSkipped(summary.skipped_files);
        }

        _renderSkipped(skippedFiles) {
            if (!skippedFiles || skippedFiles.length === 0) return;
            const warning = document.createElement("div");
            warning.className = "finance-skipped";
            warning.textContent = `⚠️ Fichier(s) ignoré(s), format illisible : ${skippedFiles.join(", ")}`;
            this.logEl.appendChild(warning);
        }
    }

    window.Lucas.FinancePanel = FinancePanel;
})();
