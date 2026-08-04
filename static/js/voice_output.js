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
    // Barge-in (ROADMAP.md §5.4 point 5) : dès que Cyril parle pendant que
    // Luca's répond à voix haute, la couper immédiatement. Seuil de volume
    // volontairement conservateur en attendant une calibration en
    // conditions réelles (téléphone, pièce, distance à la bouche — rien de
    // tout cela n'est reproductible depuis cette machine, qui n'a pas de
    // micro). À ajuster par Cyril si les faux positifs/négatifs le
    // justifient, une fois testé sur le S25 Ultra.
    const BARGE_IN_RMS_THRESHOLD = 0.09;
    // Exige un dépassement soutenu, pas un seul pic (clic, bruit bref) —
    // quelques images d'analyse consécutives plutôt qu'une durée fixe, pour
    // rester indépendant du frame rate réel de requestAnimationFrame.
    const BARGE_IN_CONSECUTIVE_FRAMES = 4;

    class VoiceOutput {
        constructor({ toggleEl, onBargeIn }) {
            this.toggleEl = toggleEl;
            this.onBargeIn = onBargeIn;
            this.enabled = window.localStorage.getItem("lucas_speak") === "1";

            // État du micro de surveillance barge-in — distinct de
            // static/js/audio.js (MicRecorder, déclenché par bouton). Ce
            // flux-ci est ouvert UNIQUEMENT pendant que Luca's parle, et
            // fermé dès la fin de la lecture : jamais de micro ouvert en
            // silence (voir CLAUDE.md règle 3, même principe appliqué ici
            // côté client).
            this._bargeInStream = null;
            this._audioCtx = null;
            this._analyser = null;
            this._bargeInRAF = null;
            this._aboveThresholdStreak = 0;

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
                // Désactiver doit couper un son déjà en cours, pas
                // seulement s'appliquer à la prochaine réponse (ROADMAP.md
                // §5.4 point 3) — sinon le bouton 🔇 ment sur ce qu'il fait
                // à l'instant où on clique dessus.
                if (!this.enabled) this.stop();
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
            // ⚠️ Bug réel trouvé le 05/08/2026 (premier vrai test audio,
            // Cyril) : le bouton 🔇 ne coupait pas le son de façon fiable.
            // Cause : le drapeau "speak" envoyé au serveur est figé au
            // moment de l'ENVOI du message (sendChat(text, voiceOutput.enabled)
            // dans app.js) — si Cyril coupe le son APRÈS l'envoi mais AVANT
            // que la réponse "speech" n'arrive (edge_tts prend plusieurs
            // secondes), ce handler s'exécutait quand même et jouait le
            // son malgré le mute entre-temps. Revérifier `this.enabled` ICI,
            // à l'instant où l'audio arrive réellement, plutôt que de se
            // fier à l'état capturé au moment de l'envoi.
            if (!this.enabled) return;
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
            this._startBargeInWatch();
        }

        // Coupe la lecture en cours — appelé par le barge-in, réutilisable
        // plus tard pour un vrai bouton mute (ROADMAP.md §5.4 point 3,
        // pas fait ici : hors périmètre de ce chantier).
        stop() {
            this.player.pause();
            this.player.currentTime = 0;
        }

        // ── Barge-in : micro de surveillance pendant la lecture ────────

        async _startBargeInWatch() {
            if (this._bargeInStream) return; // déjà en écoute
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;

            let stream;
            try {
                stream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        // Sans ça, le micro capterait la propre voix de
                        // Luca's sortant du haut-parleur du téléphone et
                        // se couperait elle-même en boucle. À vérifier en
                        // conditions réelles (voir constante ci-dessus) —
                        // l'annulation d'écho dépend du device, pas garantie
                        // à 100 % pour un <audio> hors WebRTC.
                        echoCancellation: true,
                        noiseSuppression: true,
                        // Un gain automatique amplifierait le bruit de fond
                        // en silence et fausserait le seuil fixe ci-dessus.
                        autoGainControl: false,
                    },
                });
            } catch {
                // Refusé ou indisponible — pas de barge-in cette fois, la
                // lecture continue normalement. Pas une erreur à signaler
                // à Cyril (le micro-bouton, s'il existe, redemandera).
                return;
            }

            // La lecture a pu se terminer pendant l'attente de permission —
            // ne pas laisser un micro ouvert pour rien.
            if (this.player.paused || this.player.ended) {
                stream.getTracks().forEach((track) => track.stop());
                return;
            }

            this._bargeInStream = stream;
            this._audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const source = this._audioCtx.createMediaStreamSource(stream);
            this._analyser = this._audioCtx.createAnalyser();
            this._analyser.fftSize = 512;
            source.connect(this._analyser);
            this._aboveThresholdStreak = 0;

            const data = new Uint8Array(this._analyser.fftSize);
            const tick = () => {
                if (!this._analyser) return; // watch arrêté entre-temps
                this._analyser.getByteTimeDomainData(data);
                let sumSquares = 0;
                for (let i = 0; i < data.length; i++) {
                    const normalized = (data[i] - 128) / 128;
                    sumSquares += normalized * normalized;
                }
                const rms = Math.sqrt(sumSquares / data.length);

                if (rms >= BARGE_IN_RMS_THRESHOLD) {
                    this._aboveThresholdStreak += 1;
                } else {
                    this._aboveThresholdStreak = 0;
                }

                if (this._aboveThresholdStreak >= BARGE_IN_CONSECUTIVE_FRAMES) {
                    this.stop();
                    if (this.onBargeIn) this.onBargeIn();
                    this._stopBargeInWatch();
                    return;
                }

                this._bargeInRAF = requestAnimationFrame(tick);
            };
            this._bargeInRAF = requestAnimationFrame(tick);

            // Fin naturelle de la lecture (réponse terminée, ou stop()
            // appelé) : plus besoin d'écouter.
            this.player.addEventListener("ended", () => this._stopBargeInWatch(), { once: true });
            this.player.addEventListener("pause", () => this._stopBargeInWatch(), { once: true });
        }

        _stopBargeInWatch() {
            if (this._bargeInRAF !== null) {
                cancelAnimationFrame(this._bargeInRAF);
                this._bargeInRAF = null;
            }
            this._analyser = null;
            if (this._audioCtx) {
                this._audioCtx.close().catch(() => {});
                this._audioCtx = null;
            }
            if (this._bargeInStream) {
                this._bargeInStream.getTracks().forEach((track) => track.stop());
                this._bargeInStream = null;
            }
        }
    }

    window.Lucas.VoiceOutput = VoiceOutput;
})();
