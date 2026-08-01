# core/orion_core.py — le chef d'orchestre

from config import SYSTEM_PROMPT, CLOUD_HISTORY_MESSAGES
from core.router import route, should_use_rag
from core.local_llm import ask_local
from core.cloud_llm import ask_cloud
from core.world_model import get_snapshot, format_for_prompt
from memory.memory_manager import MemoryManager
from modules.rag_manager import RAGManager


class OrionCore:
    def __init__(self):
        self.memory = MemoryManager()

    def _build_messages(self, user_message: str, destination: str = "local") -> list[dict]:
        """
        Construit la liste de messages envoyée au LLM.
        Ordre : prompt système → contexte système (World Model) →
        contexte documents (RAG, si pertinent) → historique de conversation.

        `destination` ("local" ou "cloud") restreint ce qui est joint quand la
        requête sort de la machine : pas de contexte RAG, historique tronqué.
        """
        is_cloud = destination == "cloud"

        snapshot = get_snapshot()
        system_context = format_for_prompt(snapshot)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": system_context},
        ]

        # RAG : uniquement si le routeur juge la question pertinente pour
        # les documents personnels. Évite de noyer le contexte du LLM
        # avec des extraits inutiles sur une question générale.
        # Jamais vers le cloud : les documents personnels restent locaux.
        # route() force déjà le local dans ce cas — garde redondante assumée,
        # deux verrous valent mieux qu'un sur un chemin qui sort de la machine.
        if not is_cloud and should_use_rag(user_message):
            rag_context = RAGManager().get_context(user_message)
            messages.append({"role": "system", "content": rag_context})

        history = self.memory.load_history()
        if is_cloud:
            history = history[-CLOUD_HISTORY_MESSAGES:]

        for role, content in history:
            messages.append({"role": role, "content": content})
        return messages

    def ask(self, user_message: str) -> str:
        self.memory.save_message("user", user_message)
        destination = route(user_message)
        messages = self._build_messages(user_message, destination)

        if destination == "cloud":
            answer = ask_cloud(messages)
        else:
            answer = ask_local(messages)

        self.memory.save_message("assistant", answer)
        return answer

    def prepare(self, user_message: str) -> list[dict]:
        """
        Utilisé par l'UI (LLMWorker) pour le streaming — même logique de contexte.
        Toujours "local" : LLMWorker parle directement à Ollama, le streaming
        cloud n'existe pas. À revoir si un jour le cloud est branché ici.
        """
        self.memory.save_message("user", user_message)
        return self._build_messages(user_message, "local")

    def save_response(self, answer: str):
        self.memory.save_message("assistant", answer)

    def history(self):
        return self.memory.load_history()

    def log_event(self, event_type: str, details: str = ""):
        """Expose l'enregistrement d'événements système (voir MemoryManager.save_event)."""
        self.memory.save_event(event_type, details)

    def close(self):
        self.memory.close()
