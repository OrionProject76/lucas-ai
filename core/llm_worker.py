# core/llm_worker.py — appelle Ollama dans un thread séparé
# Streaming fluide + timeout de connexion + arrêt propre

import json
import requests
from PySide6.QtCore import QThread, Signal

from config import OLLAMA_URL, MODEL_NAME, OLLAMA_CONNECT_TIMEOUT, OLLAMA_READ_TIMEOUT


class LLMWorker(QThread):
    token_received = Signal(str)        # chaque morceau de texte
    response_complete = Signal(str)     # réponse complète
    error_occurred = Signal(str)        # erreur
    started_thinking = Signal()         # connexion établie, Ollama répond

    def __init__(self, messages: list[dict]):
        super().__init__()
        self.messages = messages
        self._is_running = True

    def run(self):
        full_response = ""
        try:
            response = requests.post(
                OLLAMA_URL,
                json={"model": MODEL_NAME, "messages": self.messages, "stream": True},
                stream=True,
                timeout=(OLLAMA_CONNECT_TIMEOUT, OLLAMA_READ_TIMEOUT),
            )
            response.raise_for_status()
            
            # ✅ Connexion établie ! On peut masquer l'indicateur "connexion..."
            self.started_thinking.emit()

            for line in response.iter_lines():
                if not self._is_running:
                    break
                if not line:
                    continue
                
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                token = chunk.get("message", {}).get("content", "")
                if token:
                    full_response += token
                    self.token_received.emit(token)
                
                if chunk.get("done"):
                    break

            if self._is_running:
                self.response_complete.emit(full_response)

        except requests.exceptions.ConnectionError:
            self.error_occurred.emit(
                f"[Erreur] Impossible de contacter Ollama sur {OLLAMA_URL}. "
                "Vérifie qu'Ollama tourne (commande : ollama serve)."
            )
        except requests.exceptions.ReadTimeout:
            self.error_occurred.emit(
                "[Erreur] Ollama met trop de temps à répondre. "
                "Le modèle est peut-être en cours de chargement, réessaie."
            )
        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"[Erreur] Problème réseau avec Ollama : {e}")

    def stop(self):
        """Arrête proprement le worker en cours."""
        self._is_running = False
        self.wait(1000)