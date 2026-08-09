// static/js/conversation_mode.js — mode "conversation" mains libres
// (BRIEF_MODE_VOCAL_CONTINU_MOBILE.md). Activation/désactivation
// explicites uniquement — jamais d'état par défaut, jamais déclenché tout
// seul au démarrage de l'app.
//
// ⚠️ Distinction posée par le brief §1, à respecter à la lettre : ce n'est
// PAS de la perception continue (refusée, conditionnée à Guardian/Privacy
// Shield — VISION_LONG_TERME.md §4.2). Le micro n'est ouvert qu'entre
// start() et stop() de CETTE classe, jamais avant, jamais après, jamais en
// arrière-plan (l'app ne tourne pas hors de l'onglet actif de toute façon).
//
// Cycle : écoute (VAD, vad.js) -> enregistrement du tour détecté ->
// envoi (sendAudio, speak forcé à true) -> réponse texte puis vocale ->
// retour à l'écoute. Tour-à-tour STRICT (pas de barge-in pendant ce mode) :
// le VAD est en pause pendant qu'une réponse est traitée ou lue, pour ne
// jamais capter la propre voix de Luca's sortant du haut-parleur pendant
// qu'elle parle — même risque de rebouclage que celui déjà documenté (non
// résolu) pour le barge-in de voice_output.js, évité ici en ne l'affrontant
// simplement jamais.
//
// Le bouton fourni (toggleEl) sert À LA FOIS d'activation ET d'arrêt
// immédiat (brief §4, "bouton d'arrêt immédiat toujours visible") : il ne
// disparaît jamais tant que la page est ouverte, un second clic pendant que
// le mode est actif l'arrête sur-le-champ. Pas de second bouton distinct :
// un contrôle unique, visible en permanence, suffit à l'exigence.

window.Lucas = window.Lucas || {};

(function () {
    // Aucune parole détectée pendant cette durée alors que le mode est en
    // écoute active (hors traitement/lecture d'une réponse) -> extinction
    // automatique (brief §4). 60 s : assez long pour ne pas couper une
    // pause de réflexion normale en pleine conversation, assez court pour
    // ne pas laisser le micro ouvert indéfiniment si Cyril repose le
    // téléphone sans désactiver le mode. Non mesuré en usage réel (pas de
    // micro sur cette machine pour le tester avec une vraie voix) —
    // ajustable, même statut que les seuils de vad.js.
    const IDLE_TIMEOUT_MS = 60000;

    // Après l'arrivée du texte de la réponse, délai maximal d'attente d'un
    // audio de synthèse avant de reprendre l'écoute quand même. Couvre le
    // cas où la voix est volontairement absente (contenu sensible, Piper
    // indisponible -> "rien n'est prononcé", CLAUDE.md règle 11/TTS) : la
    // réponse texte suffit alors à clore le tour sans attendre pour rien.
    const SPEECH_GRACE_MS = 6000;

    // Alignées sur audio.js (MicRecorder) — mêmes réglages, même raisons
    // (autoGainControl explicite, echoCancellation/noiseSuppression actifs
    // pour la dictée). Dupliqué plutôt que partagé : les deux flux sont
    // indépendants (celui-ci vit tant que le mode est actif, l'autre par
    // enregistrement), factoriser ajouterait un couplage pour six lignes.
    const MIC_CONSTRAINTS = {
        audio: { autoGainControl: true, echoCancellation: true, noiseSuppression: true },
    };

    class ConversationMode {
        constructor({ toggleEl, avatar, socket, voiceOutput, micBtnEl, onNotice, onError }) {
            this.toggleEl = toggleEl;
            this.avatar = avatar;
            this.socket = socket;
            this.voiceOutput = voiceOutput;
            this.micBtnEl = micBtnEl || null;
            this.onNotice = onNotice || (() => {});
            this.onError = onError || (() => {});

            this.active = false;
            this._awaitingResponse = false;
            this._stream = null;
            this._vad = null;
            this._recorder = null;
            this._chunks = null;
            this._idleTimer = null;
            this._speechGraceTimer = null;

            toggleEl.addEventListener("click", () => this.toggle());

            // Même garde-fou que MicRecorder (audio.js) : un micro "chaud"
            // ne doit jamais rester ouvert pendant que l'onglet est masqué.
            document.addEventListener("visibilitychange", () => {
                if (document.hidden && this.active) this.stop("onglet masqué");
            });
        }

        toggle() {
            if (this.active) this.stop("manuel");
            else this.start();
        }

        async start() {
            if (this.active) return;
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                this.onError("Micro indisponible (contexte non sécurisé, ou navigateur non supporté).");
                return;
            }
            try {
                this._stream = await navigator.mediaDevices.getUserMedia(MIC_CONSTRAINTS);
            } catch (err) {
                this.onError(`Micro refusé ou indisponible : ${err.message || err}`);
                return;
            }

            this.active = true;
            if (this.micBtnEl) this.micBtnEl.disabled = true;
            this._reflect();
            this.onNotice("Mode conversation activé — parlez, Luca's répond automatiquement.");

            this._vad = new window.Lucas.VoiceActivityDetector(this._stream, {
                onSpeechStart: () => this._onSpeechStart(),
                onSpeechEnd: () => this._onSpeechEnd(),
            });
            this._vad.start();
            this._enterListening();
        }

        stop(reason) {
            if (!this.active) return;
            this.active = false;
            this._awaitingResponse = false;
            this._clearIdleTimer();
            this._clearSpeechGraceTimer();

            if (this._recorder && this._recorder.state !== "inactive") {
                this._recorder.ondataavailable = null;
                this._recorder.onstop = null;
                this._recorder.stop();
            }
            this._recorder = null;
            this._chunks = null;

            if (this._vad) {
                this._vad.stop();
                this._vad = null;
            }
            if (this._stream) {
                this._stream.getTracks().forEach((track) => track.stop());
                this._stream = null;
            }
            if (this.micBtnEl) this.micBtnEl.disabled = false;

            this._reflect();
            this.onNotice(
                reason === "inactivite"
                    ? "Mode conversation désactivé (aucune parole détectée)."
                    : "Mode conversation désactivé."
            );
        }

        // Appelé par app.js quand le texte de la réponse de Lucas arrive.
        notifyLucasReplied() {
            if (!this.active || !this._awaitingResponse) return;
            this._clearSpeechGraceTimer();
            this._speechGraceTimer = setTimeout(() => this._resumeListening(), SPEECH_GRACE_MS);
        }

        // Appelé par app.js quand la lecture de la réponse vocale se
        // termine naturellement (VoiceOutput.onPlaybackEnded).
        notifyPlaybackEnded() {
            if (!this.active || !this._awaitingResponse) return;
            this._resumeListening();
        }

        // Appelé par app.js sur toute erreur serveur (ex. parole non
        // reconnue, transcription peu fiable) pendant qu'un tour de ce
        // mode attend une réponse — sans ça, le mode resterait bloqué en
        // silence après un tour manqué au lieu de continuer à écouter.
        notifyError() {
            if (!this.active || !this._awaitingResponse) return;
            this._resumeListening();
        }

        _resumeListening() {
            this._clearSpeechGraceTimer();
            this._awaitingResponse = false;
            this._enterListening();
        }

        _enterListening() {
            if (!this.active) return;
            this.avatar.setState("listening");
            this._armIdleTimer();
            if (this._vad) this._vad.resume();
        }

        _onSpeechStart() {
            if (!this.active || this._awaitingResponse) return;
            this._clearIdleTimer();
            this.toggleEl.classList.add("capturing");
            this._chunks = [];
            this._recorder = new MediaRecorder(this._stream);
            this._recorder.addEventListener("dataavailable", (e) => {
                if (e.data && e.data.size > 0) this._chunks.push(e.data);
            });
            this._recorder.addEventListener("stop", () => this._sendTurn());
            this._recorder.start();
        }

        _onSpeechEnd() {
            if (!this.active) return;
            this.toggleEl.classList.remove("capturing");
            if (this._vad) this._vad.pause();
            if (this._recorder && this._recorder.state !== "inactive") {
                this._recorder.stop();
            }
        }

        _sendTurn() {
            if (!this.active) return;
            if (!this._chunks || this._chunks.length === 0) {
                // Déclenchement du VAD sans données exploitables (tour
                // arrêté avant la première trame) — reprendre l'écoute
                // plutôt que rester bloqué en silence.
                this._resumeListening();
                return;
            }
            const blob = new Blob(this._chunks, { type: this._recorder.mimeType });
            this._chunks = null;
            const reader = new FileReader();
            reader.onloadend = () => {
                if (!this.active) return;
                const base64 = String(reader.result).split(",", 2)[1];
                if (!base64) {
                    this._resumeListening();
                    return;
                }
                this._awaitingResponse = true;
                this.avatar.setState("thinking");
                this.voiceOutput.forgetPending();
                // speak forcé à true : le principe même du mode est une
                // réponse vocale, pas seulement affichée (brief §2, "cycle
                // automatique ... réponse vocale ... retour à l'écoute").
                this.socket.sendAudio(base64, true);
            };
            reader.readAsDataURL(blob);
        }

        _armIdleTimer() {
            this._clearIdleTimer();
            this._idleTimer = setTimeout(() => this.stop("inactivite"), IDLE_TIMEOUT_MS);
        }

        _clearIdleTimer() {
            if (this._idleTimer !== null) {
                clearTimeout(this._idleTimer);
                this._idleTimer = null;
            }
        }

        _clearSpeechGraceTimer() {
            if (this._speechGraceTimer !== null) {
                clearTimeout(this._speechGraceTimer);
                this._speechGraceTimer = null;
            }
        }

        _reflect() {
            this.toggleEl.classList.toggle("active", this.active);
            if (!this.active) this.toggleEl.classList.remove("capturing");
            this.toggleEl.title = this.active
                ? "Mode conversation activé — cliquer pour arrêter"
                : "Mode conversation (mains libres)";
        }
    }

    window.Lucas.ConversationMode = ConversationMode;
})();
