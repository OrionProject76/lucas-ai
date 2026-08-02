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
            const audio = new Audio(`data:${mime};base64,${audioBase64}`);
            audio.play().catch(() => {
                // Lecture bloquée par le navigateur (pas d'interaction
                // récente, onglet en arrière-plan...) — le texte reste
                // affiché dans le chat, ce n'est pas une panne à signaler.
            });
        }
    }

    window.Lucas.VoiceOutput = VoiceOutput;
})();
