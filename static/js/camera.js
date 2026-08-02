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
            } finally {
                stream.getTracks().forEach((track) => track.stop());
            }
        }

        _grabFrame(stream) {
            return new Promise((resolve, reject) => {
                const video = document.createElement("video");
                video.srcObject = stream;
                video.playsInline = true;

                video.addEventListener("loadedmetadata", () => {
                    video.play();
                    // Une frame après le démarrage du flux : le premier
                    // rendu est parfois noir sur mobile (auto-exposition
                    // pas encore stabilisée), une frame de marge suffit.
                    requestAnimationFrame(() => requestAnimationFrame(() => {
                        const canvas = document.createElement("canvas");
                        canvas.width = video.videoWidth;
                        canvas.height = video.videoHeight;
                        const ctx = canvas.getContext("2d");
                        ctx.drawImage(video, 0, 0);
                        const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
                        resolve(dataUrl.split(",", 2)[1]);
                    }));
                });

                video.addEventListener("error", () => reject(new Error("flux vidéo illisible")));
            });
        }
    }

    window.Lucas.CameraCapture = CameraCapture;
})();
