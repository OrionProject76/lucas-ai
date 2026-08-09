// static/js/vad.js — détection d'activité vocale (VAD), technique reprise
// de voice_output.js (barge-in) : AnalyserNode + RMS sur getByteTimeDomainData.
// Aucune autre implémentation VAD trouvée dans le projet (PC ou mobile) —
// voir cowork_workspace/BRIEF_MODE_VOCAL_CONTINU_MOBILE.md §3, exploration
// obligatoire faite avant d'écrire ce fichier.
//
// Différence avec le barge-in : ce micro capte directement la voix de
// Cyril (pas une voix rejouée par un haut-parleur puis recaptée), donc un
// niveau de signal nettement plus fort est attendu — seuil plus bas que
// BARGE_IN_RMS_THRESHOLD (0.09). Comme pour le barge-in, cette machine n'a
// pas de micro (CLAUDE.md, Priorités S1) : impossible de calibrer sur le
// vrai S25 Ultra depuis cet environnement. Point de départ raisonné,
// ajustable via les constantes ci-dessous une fois testé en conditions
// réelles — même logique que BARGE_IN_RMS_THRESHOLD en son temps.

window.Lucas = window.Lucas || {};

(function () {
    const SPEECH_RMS_THRESHOLD = 0.02;
    // Exige un dépassement soutenu avant de déclarer un début de parole —
    // évite qu'un clic ou un bruit bref ne déclenche un enregistrement.
    const SPEECH_START_CONSECUTIVE_FRAMES = 3;
    // Durée de silence continu avant de déclarer la fin d'un tour de
    // parole. 1,5 s : assez court pour ne pas ajouter un temps d'attente
    // perceptible entre une phrase et son envoi, assez long pour ne pas
    // couper au milieu d'une respiration ou d'une courte pause. Ordre de
    // grandeur usuel pour ce type de segmentation (assistants vocaux
    // grand public), pas une mesure propre à ce projet.
    const SILENCE_END_MS = 1500;
    // Garde-fou : un tour ne dépasse jamais cette durée, même si le niveau
    // sonore ne redescend jamais (bruit de fond continu, micro resté
    // ouvert par erreur, chanson à la radio...).
    const MAX_TURN_MS = 30000;

    class VoiceActivityDetector {
        constructor(stream, { onSpeechStart, onSpeechEnd, onDiagnostic } = {}) {
            this.stream = stream;
            this.onSpeechStart = onSpeechStart || (() => {});
            this.onSpeechEnd = onSpeechEnd || (() => {});
            this.onDiagnostic = onDiagnostic || null;

            this._audioCtx = null;
            this._analyser = null;
            this._data = null;
            this._raf = null;
            this._aboveStreak = 0;
            this._speaking = false;
            this._silenceStartedAt = null;
            this._turnStartedAt = null;

            this._tick = this._tick.bind(this);
        }

        // Crée le graphe audio et démarre l'analyse. Appelé une seule fois
        // par session de mode conversation — voir pause()/resume() pour
        // suspendre/reprendre sans recréer l'AudioContext à chaque tour.
        start() {
            this._audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const source = this._audioCtx.createMediaStreamSource(this.stream);
            this._analyser = this._audioCtx.createAnalyser();
            this._analyser.fftSize = 512;
            source.connect(this._analyser);
            this._data = new Uint8Array(this._analyser.fftSize);
            this._resetState();
            this._raf = requestAnimationFrame(this._tick);
        }

        // Suspend la boucle d'analyse sans démonter le graphe audio —
        // utilisé pendant qu'un tour est en cours de traitement/lecture,
        // où détecter une "parole" n'a pas de sens (et capterait la propre
        // voix de Luca's en tour-à-tour strict).
        pause() {
            if (this._raf !== null) {
                cancelAnimationFrame(this._raf);
                this._raf = null;
            }
        }

        // Reprend l'analyse pour un nouveau tour — état de segmentation
        // remis à zéro pour ne pas hériter d'un résidu du tour précédent.
        resume() {
            this._resetState();
            if (this._analyser && this._raf === null) {
                this._raf = requestAnimationFrame(this._tick);
            }
        }

        stop() {
            this.pause();
            this._analyser = null;
            this._data = null;
            if (this._audioCtx) {
                this._audioCtx.close().catch(() => {});
                this._audioCtx = null;
            }
        }

        _resetState() {
            this._aboveStreak = 0;
            this._speaking = false;
            this._silenceStartedAt = null;
            this._turnStartedAt = null;
        }

        _tick() {
            if (!this._analyser) return;
            this._analyser.getByteTimeDomainData(this._data);
            let sumSquares = 0;
            for (let i = 0; i < this._data.length; i++) {
                const normalized = (this._data[i] - 128) / 128;
                sumSquares += normalized * normalized;
            }
            const rms = Math.sqrt(sumSquares / this._data.length);
            if (this.onDiagnostic) this.onDiagnostic(rms);

            const now = performance.now();

            if (rms >= SPEECH_RMS_THRESHOLD) {
                this._aboveStreak += 1;
                this._silenceStartedAt = null;
                if (!this._speaking && this._aboveStreak >= SPEECH_START_CONSECUTIVE_FRAMES) {
                    this._speaking = true;
                    this._turnStartedAt = now;
                    this.onSpeechStart();
                }
            } else {
                this._aboveStreak = 0;
                if (this._speaking) {
                    if (this._silenceStartedAt === null) this._silenceStartedAt = now;
                    if (now - this._silenceStartedAt >= SILENCE_END_MS) {
                        this._speaking = false;
                        this.onSpeechEnd();
                        return; // la reprise se fait via resume(), pas ici
                    }
                }
            }

            if (this._speaking && now - this._turnStartedAt >= MAX_TURN_MS) {
                this._speaking = false;
                this.onSpeechEnd();
                return;
            }

            this._raf = requestAnimationFrame(this._tick);
        }
    }

    window.Lucas.VoiceActivityDetector = VoiceActivityDetector;
})();
