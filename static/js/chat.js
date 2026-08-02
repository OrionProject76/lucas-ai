// static/js/chat.js — journal de conversation et barre de saisie.

window.Lucas = window.Lucas || {};

(function () {
    class Chat {
        constructor(logEl) {
            this.logEl = logEl;
        }

        addUserMessage(text) {
            this._addBubble(text, "user");
        }

        addLucasMessage(text) {
            this._addBubble(text, "lucas");
        }

        addError(detail) {
            this._addBubble(detail, "error");
        }

        _addBubble(text, kind) {
            const bubble = document.createElement("div");
            bubble.className = `bubble ${kind}`;
            bubble.textContent = text;
            this.logEl.appendChild(bubble);
            this.logEl.scrollTop = this.logEl.scrollHeight;
        }
    }

    window.Lucas.Chat = Chat;
})();
