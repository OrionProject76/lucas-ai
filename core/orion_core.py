# core/orion_core.py — le chef d'orchestre

from config import SYSTEM_PROMPT
from core.router import route, should_use_rag
from core.local_llm import ask_local
from core.cloud_llm import ask_cloud
from core.world_model import get_snapshot, format_for_prompt
from memory.memory_manager import MemoryManager
from modules.rag_manager import RAGManager


class OrionCore:
    def __init__(self):
        self.memory = MemoryManager()

    def _build_messages(self, user_message: str) -> list[dict]:
        """
        Construit la liste de messages envoyée au LLM.
        Ordre : prompt système → contexte système (World Model) →
        contexte documents (RAG, si pertinent) → historique de conversation.
        """
        snapshot = get_snapshot()
        system_context = format_for_prompt(snapshot)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": system_context},
        ]

        # RAG : uniquement si le routeur juge la question pertinente pour
        # les documents personnels. Évite de noyer le contexte du LLM
        # avec des extraits inutiles sur une question générale.
        if should_use_rag(user_message):
            rag_context = RAGManager().get_context(user_message)
            messages.append({"role": "system", "content": rag_context})

        for role, content in self.memory.load_history():
            messages.append({"role": role, "content": content})
        return messages

    def ask(self, user_message: str) -> str:
        self.memory.save_message("user", user_message)
        destination = route(user_message)
        messages = self._build_messages(user_message)

        if destination == "cloud":
            answer = ask_cloud(messages)
        else:
            answer = ask_local(messages)

        self.memory.save_message("assistant", answer)
        return answer

    def prepare(self, user_message: str) -> list[dict]:
        """Utilisé par l'UI (LLMWorker) pour le streaming — même logique de contexte."""
        self.memory.save_message("user", user_message)
        return self._build_messages(user_message)

    def save_response(self, answer: str):
        self.memory.save_message("assistant", answer)

    def history(self):
        return self.memory.load_history()

    def log_event(self, event_type: str, details: str = ""):
        """Expose l'enregistrement d'événements système (voir MemoryManager.save_event)."""
        self.memory.save_event(event_type, details)

    def close(self):
        self.memory.close()
