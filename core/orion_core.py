# core/orion_core.py — le chef d'orchestre

from config import (
    CLOUD_HISTORY_MESSAGES,
    OCR_ENABLED,
    OCR_MAX_CHARS,
    RECENT_EVENTS_IN_PROMPT,
    SYSTEM_PROMPT,
    VISION_ENABLED,
    VISION_HISTORY_MESSAGES,
    VLM_ENABLED,
    VLM_MAX_CHARS,
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

        # La vision est décidée AVANT de charger l'historique : quand elle
        # se déclenche, l'historique doit être raccourci (voir plus bas).
        vision_context = ""
        if not is_cloud and VISION_ENABLED and should_use_vision(user_message):
            vision_context = self._describe_screen(user_message)

        history = self.memory.load_history()
        if is_cloud:
            history = history[-CLOUD_HISTORY_MESSAGES:]

        # ⚠️ ORDRE CRITIQUE — l'historique passe AVANT l'observation.
        #
        # Ces blocs étaient injectés juste après le prompt système, donc
        # avant tout l'historique. Sur une base fraîche ça ne se voyait pas :
        # l'historique était vide, l'observation se retrouvait collée à la
        # question et tout marchait. En usage réel, avec 90 messages
        # accumulés, le bloc vision arrivait en 4e position sur 91 — le
        # modèle voyait l'écran comme du contexte ancien, puis 87 tours de
        # conversation sans rapport, puis la question. Il répondait alors
        # sur une VIEILLE question de l'historique.
        #
        # C'est ce décalage qui a fait passer quatre campagnes de tests
        # pendant que l'application restait cassée : les tests utilisaient
        # une base temporaire vide.
        #
        # La question courante est le dernier message de l'historique
        # (prepare() vient de l'enregistrer). On l'isole pour glisser
        # l'observation JUSTE AVANT elle, là où elle pèse le plus.
        current_question = None
        if history and history[-1][0] == "user":
            current_question = history[-1]
            history = history[:-1]

        # ⚠️ SECONDE MOITIÉ DU MÊME BUG. Remettre le bloc au bon endroit
        # ne suffisait pas : avec 100 messages d'historique, Luca's
        # répondait encore « décris-moi ton écran » alors que le texte lu
        # était juste au-dessus de la question.
        #
        # La cause n'est pas la taille de la fenêtre de contexte. La base
        # contenait douze réponses « pourriez-vous me donner plus de
        # contexte » — des tentatives ratées précédentes. Cent messages de
        # ce motif enseignent au modèle le réflexe même qu'on corrige. Il
        # imitait sa propre mauvaise habitude.
        #
        # Mesuré : 0/9 à 100 messages, 9/9 à 6. Voir config.py.
        if vision_context and not is_cloud:
            history = history[-VISION_HISTORY_MESSAGES:]

        for role, content in history:
            messages.append({"role": role, "content": content})

        # Vision : Luca's regarde l'écran uniquement sur demande explicite.
        # Jamais vers le cloud — l'image reste locale, mais sa description
        # (« une fenêtre affichant un solde de 3200 € ») en dirait autant.
        # route() force déjà le local sur ces questions ; garde redondante
        # assumée, comme pour le RAG.
        if vision_context:
            messages.append({"role": "system", "content": vision_context})

        # RAG : uniquement si le routeur juge la question pertinente pour
        # les documents personnels. Jamais vers le cloud : les documents
        # personnels restent locaux. route() force déjà le local dans ce
        # cas — garde redondante assumée, deux verrous valent mieux qu'un
        # sur un chemin qui sort de la machine.
        # get_context() rend une chaîne VIDE quand aucun extrait n'est
        # assez proche : on n'injecte alors rien du tout.
        if not is_cloud and should_use_rag(user_message):
            rag_context = RAGManager().get_context(user_message)
            if rag_context:
                messages.append({"role": "system", "content": rag_context})

        if current_question is not None:
            messages.append(
                {"role": current_question[0], "content": current_question[1]}
            )
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
            # Une seule capture, deux lectures : l'OCR pour le texte
            # exact, le VLM pour le contexte visuel. Recapturer entre les
            # deux donnerait deux écrans différents si Cyril change de
            # fenêtre entre-temps.
            screenshot = vision.capture_screen()
        except Exception as e:  # noqa: BLE001 — voir docstring
            self.log_event("vision_failed", str(e)[:200])
            return ""

        screen_text = self._read_screen_text(screenshot)
        visual = self._describe_visual_context(vision, screenshot, user_message)

        if not screen_text and not visual:
            self.log_event("vision_failed", "ni OCR ni VLM exploitables")
            return ""

        # ⚠️ On journalise l'usage, JAMAIS le contenu. Le texte OCR est du
        # verbatim d'écran — mot de passe affiché, relevé ouvert. La table
        # d'événements ne doit pas en devenir une copie.
        self.log_event("vision_used", user_message[:80])
        return self._compose_vision_block(screen_text, visual)

    def _read_screen_text(self, screenshot: str) -> str:
        """Texte exact lu à l'écran, ou chaîne vide si l'OCR n'a rien donné."""
        if not OCR_ENABLED:
            return ""

        try:
            from modules.ocr_engine import OCREngine

            result = OCREngine().extract_text(screenshot)
        except Exception as e:  # noqa: BLE001 — un OCR absent dégrade la
            # réponse, il ne doit pas empêcher Luca's de répondre.
            self.log_event("ocr_failed", str(e)[:120])
            return ""

        if result.is_empty:
            return ""
        return result.text[:OCR_MAX_CHARS]

    def _describe_visual_context(self, vision, screenshot: str, user_message: str) -> str:
        """
        Description du VLM, ou chaîne vide s'il est désactivé ou en échec.

        Désactivé par défaut en v1.0 : llava fabrique des messages
        d'erreur absents de l'écran. Le chemin est conservé intact pour
        être réactivé en v1.1 avec internvl2 — voir config.VLM_ENABLED,
        qui documente le compromis accepté.
        """
        if not VLM_ENABLED:
            return ""

        try:
            description = vision.analyze_image(
                screenshot, self._vision_prompt(user_message)
            )
        except Exception as e:  # noqa: BLE001
            self.log_event("vision_failed", str(e)[:120])
            return ""

        if not description or description.startswith("Erreur"):
            return ""
        # Borné comme l'OCR l'est déjà : llava part parfois en description
        # de 10 000 caractères, qui noie le texte réellement lu.
        return description.strip()[:VLM_MAX_CHARS]

    @staticmethod
    def _compose_vision_block(screen_text: str, visual: str) -> str:
        """
        Assemble le bloc injecté dans le prompt.

        Le point décisif est la HIÉRARCHIE : sans elle, le LLM accorde la
        même confiance à une transcription exacte et à une description
        approximative, et invente un mélange des deux.

        ⚠️ La phrase « ne dis JAMAIS que tu ne peux pas voir » est
        conservée telle quelle : c'est elle qui a corrigé le refus de
        qwen, qui répondait « je ne peux pas voir l'écran » alors que la
        description était dans son contexte. La retirer ferait revenir le
        bug.
        """
        parts = ["TU VIENS DE REGARDER L'ÉCRAN DE CYRIL."]

        if screen_text:
            parts.append(
                "\nTexte lu à l'écran (transcription exacte, fiable) :\n"
                f"{screen_text}"
            )

        if visual:
            parts.append(
                "\nContexte visuel (application et disposition — indicatif, "
                f"peut se tromper) :\n{visual}"
            )

        if screen_text and not visual:
            # Formulé comme une consigne, pas comme une panne. En v1.0 le
            # VLM est volontairement coupé (config.VLM_ENABLED) : annoncer
            # un échec pousserait le modèle à se dédire alors qu'il a bien
            # le texte de l'écran sous les yeux.
            parts.append(
                "\nTu disposes du texte de l'écran, pas d'une description "
                "de sa disposition : appuie-toi sur le texte seul, et ne "
                "spécule pas sur l'apparence ou l'application utilisée."
            )

        parts.append(
            "\nAppuie-toi d'abord sur le texte exact pour tout ce qui est "
            "écrit ; le contexte visuel sert à situer. Ne dis JAMAIS que tu "
            "ne peux pas voir l'écran : tu viens de le faire. Si "
            "l'observation est incomplète, dis ce que tu as vu et ce qui "
            "te manque."
        )
        return "\n".join(parts)

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
