# core/lucas_core.py — le chef d'orchestre

import logging
import time
from typing import Callable

from config import (
    CLOUD_HISTORY_MESSAGES,
    HISTORY_BUDGET_CHARS,
    HISTORY_MESSAGE_MAX_CHARS,
    HISTORY_RECENT_MAX_CHARS,
    HISTORY_RECENT_MESSAGES,
    MODEL_NAME,
    OCR_ENABLED,
    OCR_MAX_CHARS,
    REANCHOR_SYSTEM_PROMPT,
    RECENT_EVENTS_IN_PROMPT,
    SYSTEM_PROMPT,
    VISION_ENABLED,
    SOURCE_HISTORY_MESSAGES,
    VLM_ENABLED,
    VLM_MAX_CHARS,
    VLM_MODEL,
)
from core.cloud_llm import ask_cloud
from core.local_llm import ask_local
from core.router import mentions_pc_explicitly, route, should_use_rag, should_use_vision
from core.world_model import (
    format_events_for_prompt,
    format_for_prompt,
    get_snapshot,
)
from memory.memory_manager import MemoryManager
from modules.rag_manager import RAGManager

# Instrumentation temporaire (03/08/2026, voir main.py) — diagnostic vision.
logger = logging.getLogger(__name__)

# Signature du callback de la console de flux (IDEAS.md #77) : (kind, texte).
ActivityCallback = Callable[[str, str], None]


def _emit(on_activity: ActivityCallback | None, kind: str, text: str) -> None:
    """
    Signale un pas du traitement, pour la console de flux — jamais
    obligatoire, jamais bloquant.

    ⚠️ Ne doit JAMAIS interrompre la réponse à Cyril. Si le callback lève
    (ex. le WebSocket s'est fermé pendant qu'on répondait), c'est un
    problème d'affichage, pas une raison de faire échouer sa question.
    """
    if on_activity is None:
        return
    try:
        on_activity(kind, text)
    except Exception:  # noqa: BLE001 — voir docstring
        pass


def fit_history_to_budget(
    history: list[tuple[str, str]],
    budget: int = HISTORY_BUDGET_CHARS,
    max_chars: int = HISTORY_MESSAGE_MAX_CHARS,
    recent: int = HISTORY_RECENT_MESSAGES,
    recent_max_chars: int = HISTORY_RECENT_MAX_CHARS,
) -> list[tuple[str, str]]:
    """
    Réduit l'historique au VOLUME DE TEXTE que le prompt système peut
    supporter sans se faire noyer, du plus récent au plus ancien.

    ⚠️ Un budget en caractères, pas un compte de messages — et ce n'est
    pas un détail d'implémentation, c'est la mesure qui l'impose : 30
    messages tronqués à 150 caractères tiennent mieux tête au prompt
    système que 6 messages bruts, tout en gardant cinq fois plus de
    contexte. Ce qui pèse, c'est le texte, pas les tours. Tableau complet
    dans config.py (HISTORY_BUDGET_CHARS).

    Le dernier échange garde une longueur plus généreuse : « Et pour
    2024 ? » n'a de sens que par rapport à la réponse qui précède.

    Au moins un message est toujours conservé : un historique réduit à
    zéro ferait perdre le fil au milieu d'une phrase, ce qui est plus
    visible pour Cyril que la dilution qu'on corrige.

    ⚠️ AUCUN marqueur de troncature n'est ajouté, et ce n'est pas un
    oubli. La première version terminait les messages coupés par « […] » —
    pour que le modèle sache que le message continuait. Trouvé en test
    réel via l'API : il RECOPIE le marqueur et coupe sa propre réponse en
    plein mot (« 2. **Interfa […] »). Mesuré : 1/9 avec le marqueur, 0/9
    sans. Tout motif régulier ajouté à l'historique est un exemple à
    imiter — c'est le même mécanisme que le bug qu'on corrige ici, appliqué
    à la forme au lieu du fond.
    """
    kept: list[tuple[str, str]] = []
    used = 0
    for index, (role, content) in enumerate(reversed(history)):
        limit = recent_max_chars if index < recent else max_chars
        if len(content) > limit:
            coupe = content[:limit]
            # Sur une frontière de mot : une coupe en plein milieu d'un mot
            # est elle aussi un motif que le modèle peut reproduire.
            espace = coupe.rfind(" ")
            content = (coupe[:espace] if espace > limit // 2 else coupe).rstrip()
        if used + len(content) > budget and kept:
            break
        kept.append((role, content))
        used += len(content)
    return list(reversed(kept))


class LucasCore:
    def __init__(self):
        self.memory = MemoryManager()

    def _build_messages(
        self,
        user_message: str,
        destination: str = "local",
        image_path: str | None = None,
        allow_screen_capture: bool = True,
        on_activity: ActivityCallback | None = None,
    ) -> list[dict]:
        """
        Construit la liste de messages envoyée au LLM.
        Ordre : prompt système → contexte système (World Model) →
        événements récents → contexte documents (RAG, si pertinent) →
        historique de conversation.

        `destination` ("local" ou "cloud") restreint ce qui est joint quand la
        requête sort de la machine : pas de contexte RAG, pas d'événements
        système, historique tronqué.

        `image_path` : photo envoyée par le téléphone (pont mobile). Quand
        elle est fournie, la vision est FORCÉE — pas besoin du classifieur
        should_use_vision(), l'appui sur le bouton caméra est déjà un signal
        sans ambiguïté. Voir _describe_camera_image().

        `allow_screen_capture` : à False pour un client où "l'écran" est
        ambigu (PWA mobile — voir api/server.py) ou carrément absent
        (Cyril peut être loin du PC). Le classifieur should_use_vision()
        continue de tourner (pour savoir SI l'intention était l'écran),
        mais la capture elle-même est refusée, et Luca's l'explique au lieu
        de se taire — jamais une capture PC silencieuse déclenchée par un
        texte dont on ne sait pas d'où il vient vraiment.

        `on_activity` : callback optionnel (kind, texte) pour la console de
        flux de la PWA (IDEAS.md #77) — voir _emit() ci-dessus.
        """
        is_cloud = destination == "cloud"

        # ⚠️ Le contexte est calculé AVANT tout, et sur l'historique privé
        # de la question courante : prepare() vient de l'enregistrer, et
        # se donner sa propre question comme « échange précédent » n'aurait
        # aucun sens. Il sert aux questions elliptiques — « Et en décembre
        # 2025 ? » n'a de sens que par rapport au tour d'avant.
        context = self.recent_context()

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
        logger.debug(
            "_build_messages(%r) : is_cloud=%s, VISION_ENABLED=%s, image_path=%r, "
            "allow_screen_capture=%s",
            user_message, is_cloud, VISION_ENABLED, image_path, allow_screen_capture,
        )
        if not is_cloud and VISION_ENABLED:
            if image_path is not None:
                vision_context = self._describe_camera_image(image_path, user_message)
                _emit(
                    on_activity, "screen_read",
                    "photo du téléphone analysée — texte trouvé (OCR)"
                    if "Texte lu à l'écran" in vision_context
                    else "photo du téléphone analysée — rien d'exploitable",
                )
            elif should_use_vision(user_message, context):
                # allow_screen_capture protège contre le déclenchement
                # ACCIDENTEL (« que peux-tu voir sur mes écrans ? » depuis
                # le téléphone, sans intention claire). Nommer le PC sans
                # ambiguïté (mentions_pc_explicitly) reste toujours
                # autorisé, quel que soit le client : la protection porte
                # sur l'ambiguïté, pas sur l'origine du message.
                if allow_screen_capture or mentions_pc_explicitly(user_message):
                    vision_context = self._describe_screen(user_message)
                    _emit(
                        on_activity, "screen_read",
                        "écran lu — texte trouvé (OCR)"
                        if "Texte lu à l'écran" in vision_context
                        else "écran lu — rien d'exploitable",
                    )
                else:
                    # ⚠️ Le classifieur dit "intention écran", mais ce
                    # client ne peut pas prouver que Cyril est devant ce
                    # PC. Le dire explicitement plutôt que capturer en
                    # silence — même principe que le RAG sans résultat
                    # plus bas : un silence laisse le modèle deviner, et
                    # deviner ici serait décrire un écran que personne n'a
                    # demandé à montrer à cet instant précis.
                    vision_context = (
                        "Cyril te parle depuis l'application mobile, pas "
                        "depuis son PC : tu N'AS PAS regardé l'écran du PC "
                        "pour cette demande, volontairement. Lire son écran "
                        "sans savoir s'il est devant serait une faute de "
                        "confidentialité, pas un détail technique.\n"
                        "Dis-le à Cyril simplement, et propose : s'il veut "
                        "que tu regardes quelque chose depuis son "
                        "téléphone, il peut utiliser le bouton caméra. "
                        "S'il parlait d'autre chose que de l'écran du PC, "
                        "réponds à ça à la place."
                    )
                    _emit(
                        on_activity, "screen_read",
                        "écran non lu — demande reçue depuis le téléphone, "
                        "sans confirmation que Cyril est devant ce PC",
                    )

        logger.debug(
            "_build_messages(%r) : vision_context final (%d caractères) = %r",
            user_message, len(vision_context), vision_context[:200],
        )

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

        # RAG : uniquement si le routeur juge la question pertinente pour
        # les documents personnels. Jamais vers le cloud : les documents
        # personnels restent locaux. route() force déjà le local dans ce
        # cas — garde redondante assumée, deux verrous valent mieux qu'un
        # sur un chemin qui sort de la machine.
        # get_context() rend une chaîne VIDE quand aucun extrait n'est
        # assez proche : on n'injecte alors rien du tout.
        rag_context = ""
        if not is_cloud and should_use_rag(user_message, context):
            rag_context = RAGManager().get_context(user_message)
            if rag_context:
                extraits = rag_context.count("[Extrait")
                _emit(
                    on_activity, "documents_searched",
                    f"documents personnels — {extraits} extrait(s) trouvé(s)"
                    if extraits
                    else "documents personnels — résultat trouvé",
                )
            if not rag_context:
                _emit(on_activity, "documents_searched", "documents personnels — aucun résultat")
                # ⚠️ NE PAS SE TAIRE. Observé en conditions réelles : sur
                # « mon salaire de juillet 2024 », dont Cyril n'a aucun
                # bulletin, rien n'était injecté — et le modèle a
                # FABRIQUÉ un nom de fichier
                # (« bulletin-de-paie-du-010724-au-310724.pdf ») et un
                # montant (1650,89 €), en imitant le format des deux
                # réponses correctes qui précédaient dans l'historique.
                # Une réponse inventée est indiscernable d'une vraie.
                #
                # Le silence laisse le modèle combler le vide. Il faut
                # donc dire explicitement que la recherche a eu lieu et
                # n'a rien donné.
                # Nommer la période manquante plutôt qu'un refus générique :
                # « aucun document pour juillet 2024 » est une information
                # que le modèle peut restituer, là où « aucun document » le
                # laisse chercher quoi dire — et donc inventer.
                from core.dates import extract_query_period

                periode = extract_query_period(user_message)
                precision = f" pour la période demandée ({periode})" if periode else ""
                rag_context = (
                    f"RECHERCHE EFFECTUÉE DANS LES DOCUMENTS DE CYRIL : "
                    f"AUCUN document ne correspond{precision}.\n\n"
                    "Ta réponse doit être : tu n'as trouvé aucun document "
                    "correspondant, et tu ne peux donc pas répondre.\n"
                    "INTERDIT : citer un montant, une date, un nom de fichier, "
                    "ou reprendre la forme d'une réponse précédente de cette "
                    "conversation. Les réponses précédentes s'appuyaient sur "
                    "des documents réels ; ici tu n'en as aucun, et un chiffre "
                    "inventé serait indiscernable d'un vrai."
                )

        # ⚠️ SECONDE MOITIÉ DU MÊME BUG, et elle vaut pour LES DEUX SOURCES.
        #
        # Remettre le bloc au bon endroit ne suffisait pas : avec 100
        # messages d'historique, Luca's répondait encore « décris-moi ton
        # écran » alors que le texte lu était juste au-dessus de la
        # question.
        #
        # La cause n'est pas la taille de la fenêtre de contexte. La base
        # contenait douze réponses « pourriez-vous me donner plus de
        # contexte » — des tentatives ratées précédentes. Cent messages de
        # ce motif enseignent au modèle le réflexe même qu'on corrige : il
        # imitait sa propre mauvaise habitude.
        # Mesuré : 0/9 à 100 messages, 9/9 à 6. Voir config.py.
        #
        # ⚠️ Le plafond n'a d'abord été appliqué qu'à la VISION, et le RAG
        # est resté cassé pour exactement la même raison — « Résume-moi
        # mon CV » recevait ses extraits sous 70 messages, et Luca's
        # demandait à Cyril de lui dicter son CV. Toute source externe
        # ajoutée ici devra passer par ce même plafond.
        if not is_cloud and (vision_context or rag_context):
            history = history[-SOURCE_HISTORY_MESSAGES:]

        # ⚠️ TROISIÈME VISAGE DU MÊME BUG, et le plus large.
        #
        # Les deux plafonds ci-dessus ne s'appliquent que dans un cas
        # précis : une requête cloud, ou une source externe injectée. Une
        # question ordinaire recevait les 100 messages en entier — et le
        # PROMPT SYSTÈME s'y noyait exactement comme s'y noyait le bloc
        # vision. Cyril l'a vu sur sa vraie conversation : la liste des
        # capacités venait d'être écrite dans SYSTEM_PROMPT, elle marchait
        # sur une conversation neuve, et restait sans effet chez lui.
        #
        # Mesuré sur DEUX règles indépendantes du prompt système — une
        # d'identité, une de sécurité (« tu n'as pas accès aux mails ») —
        # les deux tombent de 9/9 à 1/9 et 2/9 sous 100 messages. Une
        # correction question par question ne pouvait donc pas suffire.
        # Tableaux complets dans config.py.
        history = fit_history_to_budget(history)

        for role, content in history:
            messages.append({"role": role, "content": content})

        # Ré-ancrage : le prompt système répété juste avant la question.
        # Complète le budget sans le remplacer — une règle FACTUELLE se
        # rattrape par répétition (2/9 → 7/9), une règle qui lutte contre
        # le fil thématique de la conversation, non (1/9 → 1/9).
        #
        # ⚠️ Placé AVANT les blocs vision/RAG, pour ne pas les éloigner
        # de la question : leur position collée à la question est ce qui
        # les a fait fonctionner, on n'y touche pas.
        if REANCHOR_SYSTEM_PROMPT and history:
            messages.append({"role": "system", "content": SYSTEM_PROMPT})

        # Vision : Luca's regarde l'écran uniquement sur demande explicite.
        # Jamais vers le cloud — l'image reste locale, mais sa description
        # (« une fenêtre affichant un solde de 3200 € ») en dirait autant.
        # route() force déjà le local sur ces questions ; garde redondante
        # assumée, comme pour le RAG.
        if vision_context:
            messages.append({"role": "system", "content": vision_context})

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

        return self._describe_image_at(vision, screenshot, user_message)

    def _describe_camera_image(self, image_path: str, user_message: str) -> str:
        """
        Photo envoyée par le téléphone (pont mobile, Phase 4, message
        WebSocket "image" — voir api/server.py) : MÊME pipeline OCR/VLM que
        _describe_screen(), sans l'étape de capture puisque l'image existe
        déjà sur disque. Jamais un second chemin de vision parallèle — voir
        VISION_LONG_TERME.md §2 Pilier 3, précision du 02/08/2026.
        """
        try:
            from modules.vision_manager import VisionManager

            vision = VisionManager(model=VLM_MODEL)
        except Exception as e:  # noqa: BLE001 — voir _describe_screen
            self.log_event("vision_failed", str(e)[:200])
            return ""

        return self._describe_image_at(vision, image_path, user_message)

    def _describe_image_at(self, vision, image_path: str, user_message: str) -> str:
        """
        Coeur partagé : OCR + VLM sur une image déjà sur disque, qu'elle
        vienne d'une capture d'écran ou d'une photo du téléphone.
        """
        screen_text = self._read_screen_text(image_path)
        visual = self._describe_visual_context(vision, image_path, user_message)

        if not screen_text and not visual:
            self.log_event("vision_failed", "ni OCR ni VLM exploitables")
            # ⚠️ NE PAS SE TAIRE — même bug que le RAG sans résultat
            # (voir rag_context plus bas dans _build_messages). Un
            # silence ici laisse le modèle deviner, et deviner une
            # photo/capture illisible veut dire inventer un numéro, un
            # montant, un nom de commerce. Trouvé en usage réel (Cyril,
            # 02/08/2026) : une photo du téléphone sans texte exploitable
            # a produit un relevé bancaire entièrement fabriqué
            # ("123456789, VISA, 10/08/2023, Débit, 250.00, Magasin XYZ")
            # — aucune de ces valeurs n'existait sur la photo, l'OCR
            # n'avait rien trouvé du tout.
            #
            # ⚠️ Deuxième trouvaille, même jour : l'interdiction ci-dessous
            # bloque bien les faits inventés, mais pas un « par exemple »
            # hypothétique — le modèle disait honnêtement "je n'ai pas
            # accès à une image", puis illustrait quand même sa réponse
            # d'un exemple fictif ("Je vois une fenêtre Chrome affichant
            # OrangeTV"). Vérifié via les événements vision_failed
            # horodatés : aucune photo n'avait rien donné à lire, donc cet
            # exemple ne pouvait pas venir d'une vraie lecture — mais il
            # est resté troublant, car ce genre de détail peut coïncider
            # avec la réalité (le titre de la fenêtre active du PC est
            # injecté dans CHAQUE prompt, indépendamment de la vision) et
            # se lire comme une vraie observation. Et une fois généré, ce
            # même exemple s'est fait imiter mot pour mot par la réponse
            # suivante — la panne se propage.
            return (
                "TENTATIVE DE LECTURE (écran ou photo du téléphone) : "
                "AUCUN TEXTE NI CONTEXTE VISUEL EXPLOITABLE N'A ÉTÉ TROUVÉ.\n\n"
                "Ta réponse doit dire clairement que tu n'as rien pu lire "
                "d'exploitable sur cette image, et proposer de reprendre "
                "la photo ou la capture si besoin. Rien d'autre.\n"
                "INTERDIT : citer un numéro, un montant, un nom de "
                "commerce, une date ou tout autre détail — une image "
                "illisible ne permet de connaître AUCUN de ces faits, et "
                "les inventer serait indiscernable d'une vraie lecture.\n"
                "INTERDIT AUSSI : illustrer ta réponse par un exemple "
                "hypothétique du genre « par exemple, je pourrais voir... » "
                "ou « je vois actuellement... ». Même présenté comme une "
                "hypothèse, un exemple concret se lit comme une vraie "
                "observation, et n'a aucune raison d'être plus précis "
                "qu'une phrase générale."
            )

        # ⚠️ On journalise l'usage, JAMAIS le contenu. Le texte OCR est du
        # verbatim d'écran (ou de photo) — mot de passe affiché, relevé
        # ouvert, document personnel photographié. La table d'événements
        # ne doit pas en devenir une copie.
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

    def ask(
        self,
        user_message: str,
        image_path: str | None = None,
        allow_screen_capture: bool = True,
        on_activity: ActivityCallback | None = None,
    ) -> str:
        """
        `on_activity` : callback optionnel (kind, texte) pour la console de
        flux de la PWA (IDEAS.md #77). Ne change rien à la réponse ni au
        routage — voir _emit() en tête de fichier.
        """
        self.memory.save_message("user", user_message)
        destination = route(user_message, self.recent_context())
        _emit(
            on_activity, "routed",
            "question reçue — traitée en CLOUD"
            if destination == "cloud"
            else f"question reçue — traitée en LOCAL ({MODEL_NAME})",
        )
        messages = self._build_messages(
            user_message,
            destination,
            image_path=image_path,
            allow_screen_capture=allow_screen_capture,
            on_activity=on_activity,
        )

        start = time.time()
        if destination == "cloud":
            answer = ask_cloud(messages)
        else:
            answer = ask_local(messages)
        elapsed = time.time() - start
        _emit(on_activity, "answered", f"réponse prête ({elapsed:.1f} s)")

        self.memory.save_message("assistant", answer)
        return answer

    def recent_context(self) -> str:
        """
        Dernier échange, mis en forme pour le classifieur d'intention.

        ⚠️ Exposé publiquement pour que l'UI et _build_messages voient
        EXACTEMENT le même contexte. Le cache de core/intent est indexé
        sur (contexte, question) : deux contextes différents pour un même
        message, c'est deux appels au classifieur au lieu d'un.

        La question courante est exclue quand elle est déjà enregistrée —
        se donner sa propre question comme « échange précédent » n'aurait
        aucun sens.
        """
        from core.intent import format_context

        history = self.memory.load_history()
        if history and history[-1][0] == "user":
            history = history[:-1]
        return format_context(history)

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
