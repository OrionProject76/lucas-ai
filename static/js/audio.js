// static/js/audio.js — bouton micro : MediaRecorder -> base64 -> "audio" WS.
//
// ⚠️ Pas de pipeline STT séparé ici — voir VISION_LONG_TERME.md §2 Pilier 3,
// précision du 02/08/2026 : le téléphone est LA source de perception audio
// pour Luca's, mais le chemin de traitement reste UNIQUE (STTEngine côté
// serveur, api/server.py). Ce module ne fait que capter et envoyer.
//
// ⚠️ getUserMedia() exige un contexte sécurisé (https, ou localhost). Sur
// 127.0.0.1 en développement ça fonctionne ; le jour où l'API passe en
// réseau (ROADMAP.md §2) pour le vrai S25 Ultra, il faudra du TLS en plus
// du jeton — sinon le micro sera refusé par le navigateur, pas par Luca's.

window.Lucas = window.Lucas || {};

(function () {
    class MicRecorder {
        constructor(button, { onAudioReady, onError }) {
            this.button = button;
            this.onAudioReady = onAudioReady;
            this.onError = onError;
            this.mediaRecorder = null;
            this.chunks = [];
            this.recording = false;
            // ⚠️ Flux mis en cache et RÉUTILISÉ — voir _getStream() plus bas,
            // corrigé le 05/08/2026 (cause probable du micro qui perd le
            // tout début d'une phrase, confirmée en conditions réelles).
            this._stream = null;

            this.button.addEventListener("click", () => this._toggle());

            // Confidentialité : un flux gardé ouvert doit se refermer si
            // l'onglet passe en arrière-plan — jamais un micro "chaud" en
            // silence pendant que Cyril fait autre chose (même principe
            // que le flux de surveillance du barge-in, qui ne s'ouvre que
            // pendant que Luca's parle).
            document.addEventListener("visibilitychange", () => {
                if (document.hidden) this._releaseStream();
            });
        }

        async _getStream() {
            if (this._stream && this._stream.active) return this._stream;

            // ⚠️ Bug réel confirmé le 05/08/2026 (Cyril, premier vrai test
            // audio) : "qu'est-ce que tu vois sur mon écran ?" transcrit en
            // "c'est ce que tu vois sur mon écran" — cohérent avec la perte
            // de la toute première syllabe ("Qu'-"). getUserMedia() peut
            // prendre plusieurs centaines de ms à initialiser le matériel
            // audio (surtout sur Android), pendant lesquelles Cyril a déjà
            // commencé à parler. Avant ce correctif, le flux était redemandé
            // ET entièrement refermé à CHAQUE enregistrement (aucune
            // réutilisation) — chaque prise de parole repayait ce délai en
            // entier. Mis en cache : seul le tout premier enregistrement
            // d'une session paie ce coût, les suivants démarrent sur un
            // flux déjà chaud.
            this._stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    // Rendu explicite le 05/08/2026 : {audio: true} nu
                    // laissait le navigateur choisir, variable d'un
                    // appareil à l'autre. Alignement sur le flux de
                    // surveillance du barge-in (voice_output.js), déjà
                    // validé. autoGainControl reste à sa valeur par défaut
                    // (généralement activé) — contrairement au barge-in
                    // (explicitement désactivé) : la dictée profite d'une
                    // voix normalisée, le barge-in a besoin d'un gain
                    // stable pour comparer à un seuil RMS fixe — besoins
                    // opposés, pas un oubli.
                    echoCancellation: true,
                    noiseSuppression: true,
                },
            });
            return this._stream;
        }

        _releaseStream() {
            if (!this._stream) return;
            this._stream.getTracks().forEach((track) => track.stop());
            this._stream = null;
        }

        async _toggle() {
            if (this.recording) {
                this._stop();
                return;
            }

            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                this.onError(
                    "Micro indisponible (contexte non sécurisé, ou navigateur non supporté)."
                );
                return;
            }

            try {
                const stream = await this._getStream();
                this._start(stream);
            } catch (err) {
                this.onError(`Micro refusé ou indisponible : ${err.message || err}`);
            }
        }

        _start(stream) {
            this.chunks = [];
            this._recordingStartedAt = performance.now();
            this.mediaRecorder = new MediaRecorder(stream);
            this.mediaRecorder.addEventListener("dataavailable", (e) => {
                if (e.data && e.data.size > 0) this.chunks.push(e.data);
            });
            this.mediaRecorder.addEventListener("stop", () => {
                // ⚠️ Le flux n'est PLUS arrêté ici (corrigé le 05/08/2026) :
                // il est réutilisé au prochain enregistrement — voir
                // _getStream(). Il se referme uniquement si l'onglet passe
                // en arrière-plan (visibilitychange ci-dessus).
                //
                // Diagnostic (bug micro du 05/08/2026) : durée et taille
                // réelles côté client, à comparer à la durée détectée par
                // Whisper côté serveur (voir api/server.py).
                const elapsedMs = performance.now() - this._recordingStartedAt;
                const totalBytes = this.chunks.reduce((sum, c) => sum + c.size, 0);
                console.debug(
                    `[Micro] enregistrement : ${(elapsedMs / 1000).toFixed(2)}s, ` +
                    `${totalBytes} octets, mimeType=${this.mediaRecorder.mimeType}`
                );
                this._toBase64AndSend();
            });
            this.mediaRecorder.start();
            this.recording = true;
            this.button.classList.add("recording");
        }

        _stop() {
            if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
                this.mediaRecorder.stop();
            }
            this.recording = false;
            this.button.classList.remove("recording");
        }

        _toBase64AndSend() {
            if (this.chunks.length === 0) return;
            const blob = new Blob(this.chunks, { type: this.mediaRecorder.mimeType });
            const reader = new FileReader();
            reader.onloadend = () => {
                // reader.result = "data:audio/webm;base64,AAAA..." — seule la
                // partie après la virgule va à transcribe_base64().
                const base64 = String(reader.result).split(",", 2)[1];
                if (base64) this.onAudioReady(base64);
            };
            reader.readAsDataURL(blob);
        }
    }

    window.Lucas.MicRecorder = MicRecorder;
})();
