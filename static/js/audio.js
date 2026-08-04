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

            this.button.addEventListener("click", () => this._toggle());
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
                // ⚠️ Rendu explicite le 05/08/2026 (bug remonté par Cyril :
                // le micro "n'entend qu'une partie, ou mal", premier vrai
                // test audio du projet). `{audio: true}` seul laisse le
                // navigateur choisir ses réglages par défaut — variables
                // d'un appareil à l'autre. Alignement sur le flux de
                // surveillance du barge-in (voice_output.js), déjà validé :
                // echoCancellation/noiseSuppression explicites. Contrairement
                // au barge-in, autoGainControl reste ACTIVÉ ici (pas de
                // valeur explicite = comportement par défaut du navigateur,
                // généralement activé) : la dictée profite d'une voix
                // normalisée, alors que le barge-in a besoin d'un gain
                // stable pour comparer à un seuil RMS fixe — les deux flux
                // ont des besoins opposés sur ce point précis, volontaire.
                //
                // ⚠️ Cause racine du bug non confirmée à ce stade — cette
                // config ne le corrige pas forcément à elle seule. Testé et
                // écarté : décalage d'extension de fichier (.wav envoyé
                // alors que le navigateur enregistre en webm/opus) —
                // reproduit avec un vrai fichier webm/opus encodé, transcrit
                // à l'identique quel que soit le suffixe (ffmpeg détecte le
                // format réel par le contenu). Testé et écarté aussi :
                // aucune détection de fin de parole automatique n'existe
                // côté client (le micro ne s'arrête que sur un second clic
                // explicite). Instrumentation ajoutée ci-dessous et côté
                // serveur (api/server.py) pour comparer, au prochain test
                // réel, la durée réellement enregistrée à la durée détectée
                // par Whisper — sans cette donnée, corriger à l'aveugle
                // risquerait de masquer la vraie cause.
                const stream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                    },
                });
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
                stream.getTracks().forEach((track) => track.stop());
                // Diagnostic (bug micro du 05/08/2026, cause non confirmée) :
                // durée et taille réelles côté client, à comparer à la durée
                // détectée par Whisper côté serveur (voir api/server.py).
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
