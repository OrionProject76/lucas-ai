// static/js/security.js — panneau des privilèges : état de sécurité
// niveau 1, visible en permanence (IDEAS.md #78).
//
// Alimenté uniquement par le message "security_status" du serveur (voir
// api/protocol.py, security/status.py) — jamais une donnée inventée côté
// client. Un daemon éteint doit se voir clairement (pastille grise), pas
// disparaître en silence.

window.Lucas = window.Lucas || {};

(function () {
    function relativeTime(iso) {
        const diffMinutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
        if (diffMinutes < 1) return "à l'instant";
        if (diffMinutes === 1) return "il y a 1 minute";
        if (diffMinutes < 60) return `il y a ${diffMinutes} minutes`;
        const hours = Math.round(diffMinutes / 60);
        return hours === 1 ? "il y a 1 heure" : `il y a ${hours} heures`;
    }

    class SecurityBadge {
        constructor({ badgeEl, dotEl, popoverEl, textEl }) {
            this.badgeEl = badgeEl;
            this.dotEl = dotEl;
            this.popoverEl = popoverEl;
            this.textEl = textEl;
            this._open = false;

            badgeEl.addEventListener("click", () => this.toggle());
            // Un tap ailleurs referme le popover : contenu trop court pour
            // justifier un bouton "fermer" dédié, comme sur le tiroir.
            document.addEventListener("click", (event) => {
                if (
                    this._open &&
                    !badgeEl.contains(event.target) &&
                    !popoverEl.contains(event.target)
                ) {
                    this.close();
                }
            });
        }

        toggle() {
            if (this._open) this.close();
            else this.open();
        }

        open() {
            this._open = true;
            this.popoverEl.classList.add("open");
        }

        close() {
            this._open = false;
            this.popoverEl.classList.remove("open");
        }

        update({ active, last_scan_at, findings_24h, latest_summary }) {
            this.dotEl.className =
                "status-dot " + (!active ? "inactive" : findings_24h > 0 ? "warning" : "ok");

            const lines = [
                active
                    ? "Surveillance active (niveau 1)"
                    : "Surveillance inactive — daemon éteint",
            ];
            if (last_scan_at) {
                lines.push(`Dernier balayage : ${relativeTime(last_scan_at)}`);
            }
            lines.push(
                findings_24h > 0
                    ? `${findings_24h} signal(aux) sur les dernières 24h`
                    : "Aucun signal sur les dernières 24h"
            );
            if (latest_summary) {
                lines.push(`Dernier signal : ${latest_summary}`);
            }

            this.textEl.textContent = "";
            for (const line of lines) {
                const row = document.createElement("div");
                row.textContent = line;
                this.textEl.appendChild(row);
            }
        }
    }

    window.Lucas.SecurityBadge = SecurityBadge;
})();
