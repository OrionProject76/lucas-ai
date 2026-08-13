// static/js/pc_sensor.js — mode « capteur pour le PC » (brief PONT_CAPTEURS, 12/08/2026)
//
// Le téléphone sert de micro et d'appareil photo au Luca's du PC, le
// temps que le vrai matériel arrive (D-6 au catalogue). Quand ce mode est
// actif, ce que captent les capteurs part AUSSI vers la session desktop
// (api/server.py, fan-out) au lieu de rester dans la boucle mobile.
//
// ⚠️ Ce module ne touche à AUCUN pipeline de capture. Il n'ouvre pas le
// micro, ne prend pas de photo, ne parle pas au WebSocket de lui-même :
// il ne fait que porter deux drapeaux que audio.js/camera.js/
// conversation_mode.js joignent à leurs envois existants. C'est ce qui
// garantit la non-régression demandée au brief §6 — mode éteint, pas une
// ligne du chemin d'origine ne change.
//
// Les CAPTEURS seulement, pas le clavier (décision de Cyril du 12/08) :
// un « chat » tapé reste une conversation mobile ordinaire, sinon le
// téléphone cesserait d'être utilisable seul dès le mode allumé.

window.Lucas = window.Lucas || {};

(function () {
    const SENSOR_KEY = "lucas_pc_sensor";
    const TARGET_KEY = "lucas_tts_target";

    class PcSensor {
        constructor({ toggleEl, targetEl, socket, onNotice }) {
            this.toggleEl = toggleEl;
            this.targetEl = targetEl;
            this.socket = socket;
            this.onNotice = onNotice || (() => {});

            // Repris du dernier usage, comme le volume TTS et le jeton :
            // Cyril ne doit pas re-cocher son réglage à chaque ouverture
            // de la PWA. Le mode reste éteint par DÉFAUT — c'est
            // l'absence de choix antérieur qui décide, jamais un défaut
            // implicite à "actif".
            this.active = window.localStorage.getItem(SENSOR_KEY) === "1";
            this.target = window.localStorage.getItem(TARGET_KEY) === "pc" ? "pc" : "phone";

            this.toggleEl.addEventListener("click", () => this.toggle());
            this.targetEl.addEventListener("click", () => this.toggleTarget());
            this._render();

            // L'état repris du localStorage doit être annoncé au serveur :
            // sans ça, l'indicateur du PC resterait éteint alors que le
            // téléphone se croit, lui, en mode capteur — un désaccord
            // silencieux entre les deux écrans.
            if (this.active) this._announce();
        }

        // Lu par audio.js / camera.js / conversation_mode.js au moment
        // d'envoyer. Une méthode plutôt qu'un champ public : les
        // appelants ne doivent pas pouvoir modifier l'état en écrivant
        // dessus par inadvertance.
        isActive() {
            return this.active;
        }

        ttsTarget() {
            return this.target;
        }

        toggle() {
            this.active = !this.active;
            window.localStorage.setItem(SENSOR_KEY, this.active ? "1" : "0");
            this._render();
            this._announce();
            this.onNotice(
                this.active
                    ? "Capteur PC activé — ce que tu dis ou photographies arrive sur le PC."
                    : "Capteur PC désactivé — retour à la conversation mobile."
            );
        }

        toggleTarget() {
            this.target = this.target === "pc" ? "phone" : "pc";
            window.localStorage.setItem(TARGET_KEY, this.target);
            this._render();
        }

        // Sert UNIQUEMENT l'indicateur du desktop : le serveur n'a pas
        // besoin de connaître le mode à l'avance, chaque message porte
        // déjà son propre drapeau. C'est donc une notification
        // d'interface, pas un état serveur — d'où l'absence totale de
        // conséquence si elle se perd.
        _announce() {
            if (this.socket) this.socket.sendPcSensorMode(this.active);
        }

        _render() {
            this.toggleEl.textContent = this.active
                ? "📡 Capteur pour le PC : actif"
                : "📡 Capteur pour le PC";
            this.toggleEl.classList.toggle("settings-action-on", this.active);

            // Choisir où sort la voix n'a de sens que si le PC écoute :
            // hors mode capteur, la réponse sort du téléphone, point.
            this.targetEl.hidden = !this.active;
            this.targetEl.textContent =
                this.target === "pc" ? "🔈 Voix sur : PC" : "🔈 Voix sur : téléphone";
        }
    }

    window.Lucas.PcSensor = PcSensor;
})();
