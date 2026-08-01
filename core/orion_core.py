# core/orion_core.py — le chef d'orchestre

from config import (
    CLOUD_HISTORY_MESSAGES,
    RECENT_EVENTS_IN_PROMPT,
    SYSTEM_PROMPT,
    VISION_ENABLED,
    VLM_MODEL,
)
from core.cloud_llm import ask_cloud
from core.local_llm import ask_local
from core.router import route, should_use_rag, should_use_vision
from core.world_model import (
    format_events_for_prompt,
    format_for_prompt,
    get_snapshot,
)
from memory.memory_manager import MemoryManager
from modules.rag_manager import RAGManager


class OrionCore:
    def __init__(self):
        self.memory = MemoryManager()

    def _build_messages(self, user_message: str, destination: str = "local") -> list[dict]:
        """
        Construit la liste de messages envoyée au LLM.
        Ordre : prompt système → contexte système (World Model) →
        événements récents → contexte documents (RAG, si pertinent) →
        historique de conversation.

        `destination` ("local" ou "cloud") restreint ce qui est joint quand la
        requête sort de la machine : pas de contexte RAG, pas d'événements
        système, historique tronqué.
        """
        is_cloud = destination == "cloud"

        snapshot = get_snapshot()
        # Le titre de la fenêtre active ne part jamais vers le cloud : il
        # révèle sur quoi Cyril travaille (« releve_bancaire.pdf »…) même
        # quand la question posée est anodine. CPU et RAM restent joints.
        system_context = format_for_prompt(snapshot, include_window=not is_cloud)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": system_context},
        ]

        # Événements système récents : ce qui s'est passé sur la machine
        # depuis le début de la session. Jamais vers le cloud — la table
        # system_events contient des extraits de contenu sensible (voir
        # voice_manager._log), qui n'ont aucune raison de sortir.
        if not is_cloud:
            events = self.memory.load_recent_events(limit=RECENT_EVENTS_IN_PROMPT)
            events_context = format_events_for_prompt(events)
            if events_context:
                messages.append({"role": "system", "content": events_context})

        # Vision : Luca's regarde l'écran uniquement sur demande explicite.
        # Jamais vers le cloud — l'image reste locale, mais sa description
        # (« une fenêtre affichant un solde de 3200 € ») en dirait autant.
        # route() force déjà le local sur ces questions ; garde redondante
        # assumée, comme pour le RAG.
        if not is_cloud and VISION_ENABLED and should_use_vision(user_message):
            vision_context = self._describe_screen(user_message)
            if vision_context:
                messages.append({"role": "system", "content": vision_context})

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

    @staticmethod
    def _vision_prompt(user_message: str) -> str:
        """
        Transforme la question de Cyril en consigne pour le VLM.

        Le modèle vision ne connaît pas la conversation : lui donner la
        question brute suffit, mais il faut lui rappeler qu'il regarde
        une capture d'écran et qu'il doit répondre en français — llava
        bascule spontanément en anglais sinon.
        """
        return (
            "Voici une capture de l'écran de l'utilisateur. "
            "Décris CONCRÈTEMENT ce qui est affiché : applications ouvertes, "
            "titres de fenêtres, textes lisibles, messages d'erreur, chiffres. "
            "Cite les mots que tu lis plutôt que de les paraphraser. "
            f"Réponds en français à sa question : {user_message}"
        )

    def _describe_screen(self, user_message: str) -> str:
        """
        Capture l'écran et le fait décrire par le VLM local.

        ⚠️ Coût mesuré sur cette machine : **~25 s au premier appel**, le
        temps qu'Ollama charge llava en VRAM, puis **~0,8 s** tant que le
        modèle reste chaud. Réduire la capture (4K → 1080p) ne change
        rien : llava redimensionne en interne. Ollama décharge le modèle
        après quelques minutes d'inactivité, donc l'attente de 25 s
        revient périodiquement — c'est pour ça que l'UI construit le
        contexte dans un thread (voir ui.main_window.ContextWorker).

        Retourne une chaîne vide en cas d'échec plutôt que de propager :
        une vision indisponible doit dégrader la réponse, pas empêcher
        Luca's de répondre du tout.
        """
        try:
            from modules.vision_manager import VisionManager

            vision = VisionManager(model=VLM_MODEL)
            # On transmet la vraie question au VLM plutôt qu'un « décris
            # cette image » générique. « C'est quoi cette erreur ? »
            # obtient une réponse ciblée ; la description passe-partout
            # obligerait le LLM principal à deviner ce qui compte dans un
            # écran entier, et perdrait justement le détail demandé.
            description = vision.analyze_image(
                vision.capture_screen(), self._vision_prompt(user_message)
            )
        except Exception as e:  # noqa: BLE001 — voir docstring
            self.log_event("vision_failed", str(e)[:200])
            return ""

        if not description or description.startswith("Erreur"):
            self.log_event("vision_failed", description[:200])
            return ""

        self.log_event("vision_used", user_message[:80])
        # ⚠️ Le bloc doit DONNER UN ORDRE, pas seulement décrire. Rédigé
        # comme un simple constat, qwen l'ignorait et répondait « je ne
        # peux pas voir l'écran » — alors que la description était juste
        # au-dessus dans son contexte. Un modèle de texte affirme par
        # défaut qu'il n'a pas d'yeux ; il faut le contredire
        # explicitement.
        return (
            "TU VIENS DE REGARDER L'ÉCRAN DE CYRIL. Voici ce que tu y as vu :\n"
            f"{description}\n"
            "Réponds à sa question en t'appuyant sur cette observation. "
            "Ne dis JAMAIS que tu ne peux pas voir l'écran : tu viens de le "
            "faire. Si l'observation est incomplète, dis ce que tu as vu et "
            "ce qui te manque."
        )

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
