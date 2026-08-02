// static/js/voice_output.js — lecture des réponses vocales de Luca's.
//
// Le serveur route et synthétise (edge_tts ou Piper, voir
// core/router.route_voice(), modules/voice_manager.py) et renvoie l'audio
// en base64 ("speech", voir api/protocol.py) — ce module ne fait que
// décoder et jouer, jamais de synthèse côté client.
//
// Désactivé par défaut : même choix que le toggle « TTS Auto » de l'UI
// PySide6 (ui/main_window.py, tts_auto = False). La voix ne doit jamais
// se déclencher sans que Cyril l'ait explicitement demandée.

window.Lucas = window.Lucas || {};

(function () {
    class VoiceOutput {
        constructor({ toggleEl }) {
            this.toggleEl = toggleEl;
            this.enabled = window.localStorage.getItem("lucas_speak") === "1";

            // ⚠️ UN SEUL élément, créé une fois et réutilisé — jamais un
            // `new Audio()` par appel. Trouvé en usage réel (Cyril,
            // 02/08/2026) : le son démarrait puis coupait net après une
            // syllabe, sans erreur. Mesuré (Chrome, instrumentation
            // complète des événements média) : le fichier reçu est
            // intact — un fichier tronqué aurait joué plusieurs secondes
            // valides avant de s'arrêter, pas coupé après un fragment.
            // La seule autre explication tenant compte des faits : un
            // `Audio()` construit en variable locale et jamais référencé
            // ailleurs devient éligible au ramasse-miettes PENDANT la
            // lecture — un piège documenté de l'API, plus agressif sur
            // mobile (mémoire contrainte) que sur bureau. En le gardant
            // sur `this.player`, l'objet survit aussi longtemps que
            // l'instance elle-même (donc toute la session).
            this.player = new Audio();
            this.player.addEventListener("error", () => {
                // Pas de son plutôt qu'une erreur qui remonte — le texte
                // reste affiché dans le chat.
            });

            this._reflect();

            toggleEl.addEventListener("click", () => {
                this.enabled = !this.enabled;
                window.localStorage.setItem("lucas_speak", this.enabled ? "1" : "0");
                this._reflect();
            });
        }

        _reflect() {
            this.toggleEl.textContent = this.enabled ? "🔊" : "🔇";
            this.toggleEl.title = this.enabled
                ? "Réponses vocales activées"
                : "Réponses vocales désactivées";
        }

        play(audioBase64, mime) {
            if (!audioBase64) return;
            // Une réponse qui arrive pendant que la précédente joue encore
            // interrompt celle-ci et prend le relais — comportement voulu,
            // pas un effet de bord : la dernière réponse de Cyril est
            // toujours celle qui compte.
            this.player.src = `data:${mime};base64,${audioBase64}`;
            this.player.play().catch(() => {
                // Lecture bloquée par le navigateur (pas d'interaction
                // récente, onglet en arrière-plan...) — le texte reste
                // affiché dans le chat, ce n'est pas une panne à signaler.
            });
        }
    }

    window.Lucas.VoiceOutput = VoiceOutput;
})();
