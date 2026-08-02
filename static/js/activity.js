// static/js/activity.js — console de flux (IDEAS.md #77).
//
// Affiche ce que Luca's fait VRAIMENT avant de répondre : local ou cloud,
// écran lu ou non, documents cherchés et trouvés ou non. Différent de
// l'avatar (qui montre un état de présence, pas un fait vérifiable) —
// voir api/protocol.py, activity().
//
// Repliée par défaut : ne mange rien à la conversation tant que Cyril ne
// la demande pas.

window.Lucas = window.Lucas || {};

(function () {
    const ICONS = {
        routed: "🧭",
        screen_read: "🖥️",
        documents_searched: "📄",
        answered: "✅",
        voice: "🔊",
    };

    function timestamp() {
        return new Date().toLocaleTimeString("fr-FR", { hour12: false });
    }

    class ActivityConsole {
        constructor({ toggleEl, drawerEl, closeEl, logEl, badgeEl }) {
            this.drawerEl = drawerEl;
            this.logEl = logEl;
            this.badgeEl = badgeEl;
            this._open = false;

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
            this.badgeEl.classList.remove("visible");
        }

        close() {
            this._open = false;
            this.drawerEl.classList.remove("open");
        }

        add(kind, text) {
            const line = document.createElement("div");
            line.className = "activity-line";

            const time = document.createElement("span");
            time.className = "activity-time";
            time.textContent = timestamp();

            const icon = document.createElement("span");
            icon.className = "activity-icon";
            icon.textContent = ICONS[kind] || "•";

            const label = document.createElement("span");
            label.className = "activity-text";
            label.textContent = text;

            line.append(time, icon, label);
            this.logEl.appendChild(line);
            this.logEl.scrollTop = this.logEl.scrollHeight;

            // Pastille discrète tant que Cyril n'a pas ouvert le tiroir —
            // même logique que le badge d'app iOS/Android : signale sans
            // interrompre.
            if (!this._open) this.badgeEl.classList.add("visible");
        }
    }

    window.Lucas.ActivityConsole = ActivityConsole;
})();
