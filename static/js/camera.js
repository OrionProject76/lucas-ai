// static/js/camera.js — bouton caméra : capture une photo -> base64 -> "image" WS.
//
// ⚠️ Pas de pipeline vision séparé ici — voir VISION_LONG_TERME.md §2
// Pilier 3, précision du 02/08/2026 : le téléphone est LA source de
// perception visuelle pour Luca's, mais le traitement (OCR, VLM si activé)
// reste le pipeline UNIQUE déjà existant côté serveur (core.LucasCore).
// Ce module ne fait que capter une image fixe et l'envoyer.
//
// Une seule photo par appui, pas un flux vidéo continu : le pipeline
// serveur (OCR + VLM optionnel) traite une image à la fois, comme pour
// une capture d'écran — un flux permanent n'apporterait rien de plus et
// coûterait la batterie du téléphone pour rien.

window.Lucas = window.Lucas || {};

(function () {
    class CameraCapture {
        constructor(button, { onImageReady, onError }) {
            this.button = button;
            this.onImageReady = onImageReady;
            this.onError = onError;
            this.button.addEventListener("click", () => this._capture());
        }

        async _capture() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                this.onError(
                    "Caméra indisponible (contexte non sécurisé, ou navigateur non supporté)."
                );
                return;
            }

            let stream;
            try {
                stream = await navigator.mediaDevices.getUserMedia({
                    video: { facingMode: "environment" },
                });
            } catch (err) {
                this.onError(`Caméra refusée ou indisponible : ${err.message || err}`);
                return;
            }

            try {
                const base64 = await this._grabFrame(stream);
                if (base64) this.onImageReady(base64);
            } catch (err) {
                // ⚠️ Sans ce catch, un rejet de _grabFrame() devenait une
                // promesse non gérée — silencieuse pour Cyril. Trouvé en
                // usage réel (02/08/2026) : la caméra "s'éteignait seule"
                // sans un mot d'explication, et zéro message n'atteignait
                // jamais le serveur (aucune capture n'avait réellement
                // abouti).
                this.onError(`Capture échouée : ${err.message || err}`);
            } finally {
                stream.getTracks().forEach((track) => track.stop());
            }
        }

        _grabFrame(stream) {
            return new Promise((resolve, reject) => {
                // ⚠️ Attaché au DOM, hors écran mais jamais visible — même
                // correctif que static/js/voice_output.js pour l'audio :
                // un élément média jamais inséré dans le DOM peut être
                // déprioritisé ou coupé par le navigateur avant d'aboutir.
                // Un `<video>` purement en mémoire (comme avant) fonctionne
                // sur certains navigateurs mais pas de façon fiable sur
                // mobile.
                const video = document.createElement("video");
                video.srcObject = stream;
                video.playsInline = true;
                video.muted = true;
                video.style.position = "fixed";
                video.style.top = "-9999px";
                video.style.width = "1px";
                video.style.height = "1px";
                document.body.appendChild(video);

                let settled = false;
                const finish = (fn, value) => {
                    if (settled) return;
                    settled = true;
                    video.remove();
                    fn(value);
                };

                // Filet de sécurité : sans lui, un flux qui ne charge
                // jamais laissait Cyril devant un bouton qui "s'éteint"
                // sans explication, indéfiniment.
                const timeout = setTimeout(
                    () => finish(reject, new Error("caméra sans réponse (délai dépassé)")),
                    8000
                );

                // Le flux peut s'arrêter avant même d'avoir chargé une
                // frame (permission révoquée, caméra reprise par une autre
                // appli...) — c'était exactement la cause du silence
                // complet observé avant ce correctif.
                stream.getVideoTracks().forEach((track) => {
                    track.addEventListener("ended", () => {
                        clearTimeout(timeout);
                        finish(reject, new Error("le flux caméra s'est arrêté avant la capture"));
                    });
                });

                video.addEventListener("loadedmetadata", () => {
                    video.play();
                    // Une frame après le démarrage du flux : le premier
                    // rendu est parfois noir sur mobile (auto-exposition
                    // pas encore stabilisée), une frame de marge suffit.
                    requestAnimationFrame(() => requestAnimationFrame(() => {
                        clearTimeout(timeout);
                        const canvas = document.createElement("canvas");
                        canvas.width = video.videoWidth;
                        canvas.height = video.videoHeight;
                        const ctx = canvas.getContext("2d");
                        ctx.drawImage(video, 0, 0);
                        const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
                        finish(resolve, dataUrl.split(",", 2)[1]);
                    }));
                });

                video.addEventListener("error", () => {
                    clearTimeout(timeout);
                    finish(reject, new Error("flux vidéo illisible"));
                });
            });
        }
    }

    window.Lucas.CameraCapture = CameraCapture;
})();
