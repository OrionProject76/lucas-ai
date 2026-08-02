// static/js/avatar.js — avatar 2D léger, canvas.
//
// Palette et logique reprises de ui/avatar_widget.py (PySide6), pas
// réinventées : les trois clients (PySide6, Godot, PWA) doivent se
// ressembler visuellement pour la même Luca's. En particulier, l'ambre de
// WATCHING est un CHOIX DE SÉCURITÉ (témoin de capture d'écran, comme la
// LED d'une webcam) — jamais une variation esthétique libre.

window.Lucas = window.Lucas || {};

(function () {
    const STATE_LABELS = {
        idle: "prête",
        thinking: "réfléchit",
        speaking: "parle",
        watching: "regarde",
        listening: "écoute",
    };

    // Dégradés radiaux par état : (position, r, g, b, alpha). Identiques à
    // HALO_PALETTES dans ui/avatar_widget.py.
    const HALO_PALETTES = {
        idle: [[0.0, 0, 212, 255, 70], [0.55, 90, 120, 240, 30], [1.0, 124, 58, 237, 0]],
        thinking: [[0.0, 160, 90, 255, 140], [0.5, 124, 58, 237, 70], [1.0, 70, 20, 160, 0]],
        speaking: [[0.0, 0, 230, 255, 110], [0.5, 60, 160, 255, 60], [1.0, 124, 58, 237, 0]],
        watching: [[0.0, 255, 200, 60, 170], [0.45, 255, 150, 0, 90], [1.0, 200, 90, 0, 0]],
        listening: [[0.0, 0, 255, 220, 130], [0.5, 0, 200, 255, 60], [1.0, 0, 120, 200, 0]],
    };

    const BREATH_AMPLITUDE = 2.2;
    const TRANSITION_MS = 250; // aligné sur TRANSITION_FRAMES (5 @ 20fps) de PySide6

    function rgba([, r, g, b, a]) {
        return `rgba(${r}, ${g}, ${b}, ${a / 255})`;
    }

    class Avatar {
        constructor(canvas, labelEl) {
            this.ctx = canvas.getContext("2d");
            this.size = canvas.width;
            this.labelEl = labelEl;
            this.state = "idle";
            this.transitionStart = 0;
            this.breathPhase = Math.random() * Math.PI * 2;
            // Point témoin clignotant, propre à WATCHING — le halo ambre
            // seul ne se remarquait pas assez (même constat que côté
            // PySide6).
            this.watchPulse = 0;
            requestAnimationFrame((t) => this._loop(t));
        }

        setState(state) {
            if (!HALO_PALETTES[state]) state = "idle";
            if (state === this.state) return;
            this.state = state;
            this.transitionStart = performance.now();
            this.labelEl.textContent = STATE_LABELS[state] || "";
        }

        _loop(t) {
            this.breathPhase += 0.02;
            this.watchPulse += 0.08;
            this._draw(t);
            requestAnimationFrame((next) => this._loop(next));
        }

        _draw(t) {
            const { ctx, size } = this;
            ctx.clearRect(0, 0, size, size);

            const cx = size / 2;
            const cy = size / 2;
            const breath = Math.sin(this.breathPhase) * BREATH_AMPLITUDE;
            const radius = size * 0.42 + breath;

            const elapsed = performance.now() - this.transitionStart;
            const alphaScale = Math.min(1, elapsed / TRANSITION_MS);

            const palette = HALO_PALETTES[this.state];
            const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
            for (const stop of palette) {
                const [pos, r, g, b, a] = stop;
                gradient.addColorStop(pos, `rgba(${r}, ${g}, ${b}, ${(a / 255) * alphaScale})`);
            }
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(cx, cy, radius, 0, Math.PI * 2);
            ctx.fill();

            // Coeur du visage : un cercle plein, plus discret que le halo.
            ctx.fillStyle = "rgba(10, 30, 40, 0.85)";
            ctx.beginPath();
            ctx.arc(cx, cy, radius * 0.55, 0, Math.PI * 2);
            ctx.fill();

            // Yeux simples.
            ctx.fillStyle = rgba(palette[0]);
            const eyeY = cy - radius * 0.08;
            const eyeR = size * 0.035;
            for (const dx of [-radius * 0.22, radius * 0.22]) {
                ctx.beginPath();
                ctx.arc(cx + dx, eyeY, eyeR, 0, Math.PI * 2);
                ctx.fill();
            }

            // Témoin WATCHING : point clignotant en haut à droite du halo,
            // seconde couche de signal en plus de la couleur ambre — même
            // raison que côté PySide6 (l'ambre seul ne se voit pas assez en
            // périphérie du champ visuel).
            if (this.state === "watching") {
                const pulse = (Math.sin(this.watchPulse) + 1) / 2;
                ctx.fillStyle = `rgba(255, 170, 0, ${0.4 + 0.6 * pulse})`;
                ctx.beginPath();
                ctx.arc(cx + radius * 0.75, cy - radius * 0.75, 5, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }

    window.Lucas.Avatar = Avatar;
})();
