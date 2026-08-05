# core/lucas_core.py — le chef d'orchestre

import re
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
    REASONING_ENGINE_ENABLED,
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
from core.aura_modes import AuraModeEngine, tone_hint
from core.memory_weighting import annotate_uncertain_events, annotate_uncertain_history
from core.reasoning_engine import ReasoningEngine
from core.router import (
    extract_app_name,
    extract_calculation,
    extract_city,
    looks_like_app_request,
    mentions_pc_explicitly,
    route,
    should_use_automation,
    should_use_calculator,
    should_use_finance,
    should_use_rag,
    should_use_vision,
    should_use_weather,
    should_use_websearch,
)
from core.text_utils import normalize
from core.world_model import (
    format_events_for_prompt,
    format_for_prompt,
    get_snapshot,
)
from memory.memory_manager import MemoryManager
from modules.rag_manager import RAGManager

# ⚠️ modules.finance_manager est importé PARESSEUSEMENT dans
# _build_messages(), pas ici : il importe modules.finance_categorizer,
# qui importe core.text_utils — un import en tête fermerait la boucle,
# core/__init__ chargeant LucasCore avant que ce module ait fini de se
# charger. Même motif que core.dates dans modules/rag_manager.py.

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


# ⚠️ Filtre heuristique par mots-clés/regex — PAS une solution robuste
# définitive. Premier passage pragmatique, cohérent avec le reste du
# projet (MVP puis itération). Une fois le schéma mémoire
# confiance/provenance implémenté (IDEAS.md #2bis), ce filtrage pourra se
# faire proprement via une métadonnée (ex. un type "vision_refusal" posé
# à l'écriture) plutôt que par correspondance de texte sur la réponse
# après coup — pas encore construit, ce lien n'est pas fait ici.
#
# Motifs tirés des formulations RÉELLEMENT observées le 03/08/2026 (voir
# real_vision_test*.py, session précédente) : 3 refus capturés sur la
# vraie base de Cyril, plus un 4e reproduit en direct sur une copie de
# cette même base. Comparés après normalize() (minuscules, sans accents,
# apostrophes uniformisées — voir core/text_utils.py) pour ne pas
# dépendre d'une casse ou d'un accent exacts.
# ⚠️ Élargi le 05/08/2026 après la bascule sur gpt-oss:20b.
#
# Ces motifs avaient été écrits en observant qwen2.5:7b. Confrontés aux
# formulations RÉELLES du nouveau modèle, ils attrapaient **0 refus sur
# 6** — le filtre était devenu entièrement aveugle sans qu'aucun test ne
# le signale, puisqu'aucun test ne confronte une expression régulière au
# vocabulaire d'un modèle qui n'existait pas quand elle a été écrite.
#
# Formulations réellement produites par gpt-oss, toutes ratées :
#   « je ne peux pas voir ce qu'il y a à ton écran »
#   « je n'ai aucun moyen de voir ce qui se passe sur ton écran »
#   « je n'ai aucune visibilité sur ce qui s'affiche »
#   « il m'est totalement impossible de voir ce qui se passe »
#   « sans accès à ton poste je ne peux pas voir »
#
# Les motifs sont donc découpés en deux idées combinées plutôt qu'en
# phrases entières : une NÉGATION DE CAPACITÉ, et une MENTION DE L'ÉCRAN.
# Une phrase entière est un piège — elle ne survit pas au premier
# changement de modèle, ce que cet épisode démontre.
_REFUS_CAPACITE = (
    # `\w* ?` autorise un adverbe intercalé — « je n'ai MALHEUREUSEMENT
    # aucun moyen », « je n'arrive VRAIMENT pas à ». Observé chez gpt-oss,
    # et invisible pour un motif qui colle les mots deux à deux.
    r"(?:ne peux pas|ne suis pas en mesure|n'ai \w* ?pas acces|"
    r"n'ai \w* ?aucun[e]? (?:acces|moyen|visibilite|maniere|facon)|"
    r"impossible de|ne peux rien|sans acces|n'arrive \w* ?pas a|ne vois rien)"
)
_MENTION_ECRAN = r"(?:ecran|affich|ton poste|contexte visuel|image|ce que tu vois)"

VISION_REFUSAL_PATTERNS = [
    # Négation puis mention de l'écran, dans un rayon raisonnable — assez
    # large pour « je ne peux pas voir ce qu'il y a à ton écran », assez
    # étroit pour ne pas relier deux phrases sans rapport.
    rf"{_REFUS_CAPACITE}.{{0,60}}{_MENTION_ECRAN}",
    # L'ordre inverse : « à l'écran, je ne peux pas voir ».
    rf"{_MENTION_ECRAN}.{{0,40}}{_REFUS_CAPACITE}",
    # Formulations historiques, conservées telles quelles.
    r"ne peux pas regarder a distance",
    r"fonctionne localement.*ne peux pas regarder",
]


def is_vision_refusal(content: str) -> bool:
    """Ce tour ressemble-t-il à un refus de vision déjà observé en réel ?"""
    normalized = normalize(content)
    return any(re.search(pattern, normalized) for pattern in VISION_REFUSAL_PATTERNS)


# ── Garde-fou : jamais confirmer une action qui n'a pas eu lieu ────────
#
# ⚠️ Pourquoi un contrôle DÉTERMINISTE et pas seulement une consigne de
# prompt (« INTERDIT d'affirmer... », injectée juste au-dessus) ?
#
# Parce que ce projet a DÉJÀ MESURÉ que les consignes de prompt cèdent
# sous un historique long : la règle de sécurité « refuse de consulter ma
# boîte mail » passe de 9/9 sans historique à 2/9 avec 100 messages
# (§5.29). Une consigne suffit pour orienter une réponse ; elle ne suffit
# pas pour GARANTIR qu'une affirmation sur l'état réel de la machine de
# Cyril est vraie. Cyril l'a formulé exactement ainsi : « Luca ne doit
# JAMAIS confirmer une action comme réussie sans un vrai retour de succès
# du code d'exécution. »
#
# Ce contrôle-ci ne dépend d'aucun modèle : il compare ce que la réponse
# AFFIRME à ce que le code a RÉELLEMENT exécuté (self._action_executed,
# posé uniquement quand DecisionEngine a rendu la main sans exception).
#
# Il AJOUTE une correction plutôt que de réécrire la réponse : réécrire
# supposerait de savoir ce que Luca's voulait dire, ajouter se contente
# de rétablir le fait. Le texte trompeur reste visible — c'est voulu :
# Cyril doit pouvoir constater l'écart, pas le découvrir plus tard.
# ⚠️ Élargi le 05/08/2026 après la bascule sur gpt-oss:20b, et pour la
# même raison que VISION_REFUSAL_PATTERNS plus haut : ces motifs avaient
# été écrits en observant qwen2.5. Face aux formulations réelles du
# nouveau modèle, ils attrapaient **1 fausse confirmation sur 6**, puis
# **0 sur 6** au second tirage.
#
# Un garde-fou qui cesse de détecter ne produit aucune erreur visible. Il
# redevient simplement silencieux — et c'est le pire mode de défaillance
# pour un mécanisme dont toute la raison d'être est de rattraper un
# mensonge.
#
# Ce que gpt-oss écrit, et que l'ancienne version ratait :
#   « Bloc-notes ouvert sur ton PC. »        <- participe SEUL, pas de verbe
#   « Bloc-notes lancé sur ton PC ! »        <- idem
#   « Le bloc-notes est déjà lancé. »        <- « déjà » absent des adverbes
#   « J'ai mis le Bloc-Notes en marche. »    <- tournure inconnue
_ADVERBES = r"(?:bien |donc |deja |maintenant |desormais |a present )*"
_PARTICIPES = r"(?:lance|lancee|ouvert|ouverte|demarre|demarree|active|activee)"
_APPS = r"(?:bloc-?notes?|notepad|chrome|explorateur|calculatrice|application)"

_CLAIMED_ACTION_SUCCESS = re.compile(
    r"(?:"
    rf"\best {_ADVERBES}{_PARTICIPES}\b"
    rf"|\ba ete {_ADVERBES}{_PARTICIPES}\b"
    rf"|\bj'ai {_ADVERBES}(?:{_PARTICIPES}|mis)\b"
    rf"|\bje l'ai {_ADVERBES}{_PARTICIPES}\b"
    # « vient/viens de » aux deux personnes, et la forme pronominale
    # « vient tout juste de s'ouvrir » que gpt-oss emploie souvent.
    r"|\bvien[st] (?:tout juste )?d(?:e |')(?:s')?(?:ouvrir|lancer|demarrer)\b"
    rf"|\bvient d'etre {_ADVERBES}{_PARTICIPES}\b"
    r"|\ben marche\b"
    r"|\bvoila (?:le |la )?(?:bloc|notepad|chrome|explorateur|calculatrice)"
    # ⚠️ Le participe SEUL, sans verbe : « Bloc-notes ouvert sur ton PC. »
    # C'est la forme que gpt-oss privilégie, et celle qu'aucun motif
    # construit autour d'un verbe ne pouvait attraper. Exige le nom d'une
    # application juste avant, pour ne pas déclencher sur « le fichier
    # ouvert » ou « le dossier lancé » au fil d'une phrase.
    rf"|\b{_APPS}\s+{_ADVERBES}{_PARTICIPES}\b"
    r")"
)

FALSE_CLAIM_CORRECTION = (
    "\n\n⚠️ *Correction automatique : aucune action n'a réellement été "
    "exécutée sur ton PC pour ce message. La phrase ci-dessus est fausse — "
    "elle vient du modèle, pas du code d'exécution. Rien n'a été lancé.*"
)


def claims_action_success(answer: str) -> bool:
    """
    La réponse affirme-t-elle qu'une application a été lancée/ouverte ?

    Volontairement centrée sur l'AFFIRMATION D'ÉTAT (« est lancé », « j'ai
    ouvert »), pas sur l'intention (« je vais ouvrir ») : une intention
    annoncée n'est pas un mensonge sur ce qui s'est passé, et la corriger
    produirait du bruit sur des réponses honnêtes.
    """
    return bool(_CLAIMED_ACTION_SUCCESS.search(normalize(answer)))


class LucasCore:
    def __init__(self):
        self.memory = MemoryManager()

    @property
    def aura(self) -> AuraModeEngine:
        """
        Moteur AURA, construit à la première demande.

        Son état « collant » (Deep Focus) est lu et écrit via la mémoire,
        pas via un attribut : LucasCore est recréé à chaque requête, un
        drapeau en RAM ne survivrait pas au message suivant (voir
        core/aura_modes.py::AuraModeEngine).

        Paresseux et non construit dans __init__ à dessein : plusieurs
        tests instancient `LucasCore.__new__(LucasCore)` avec une mémoire
        factice, sans jamais passer par __init__. Un attribut posé dans
        __init__ les cassait tous ; une propriété garde le cœur
        constructible sans base réelle, ce qui est la raison d'être de ce
        motif de test.
        """
        if getattr(self, "_aura", None) is None:
            self._aura = AuraModeEngine(
                store=(
                    lambda: self.memory.get_state("aura_deep_focus"),
                    lambda value: self.memory.set_state("aura_deep_focus", value),
                )
            )
        return self._aura

    def _describe_presence(self, snapshot: dict) -> str:
        """
        Bloc [Contexte] : ce que fait Cyril, et depuis quand ils se parlent.

        Matière première de la variation de ton (SYSTEM_PROMPT, section
        « Ta façon de parler ») — le prompt dit d'en tenir compte sans
        jamais le réciter. Rendre une chaîne vide quand il n'y a rien à
        dire est délibéré : une ligne « aucun mode détecté, aucun échange
        récent » n'apprendrait rien au modèle et ne ferait que diluer le
        prompt système, ce qui est mesuré comme un vrai risque ici (§5.29).
        """
        morceaux: list[str] = []

        mode = self.aura.detect(
            snapshot.get("active_window", ""), snapshot.get("active_process", "")
        )
        indication = tone_hint(mode)
        if indication:
            morceaux.append(indication)

        # ⚠️ Formulé SANS « vous » ni « tu ». Première rédaction : « C'est
        # votre premier échange » — un bloc censé servir la variation de ton
        # écrivait lui-même du vouvoiement dans le prompt, juste au-dessus
        # d'une règle qui l'interdit. Le prompt ne doit modéliser aucune
        # forme d'adresse qu'il ne veut pas voir ressortir.
        minutes = self.memory.minutes_since_last_exchange()
        if minutes is None:
            morceaux.append("Premier échange enregistré avec Cyril.")
        elif minutes < 10:
            morceaux.append("Conversation déjà en cours avec Cyril.")
        elif minutes > 720:
            morceaux.append("Dernier échange avec Cyril il y a plus de douze heures.")

        if not morceaux:
            return ""
        return "[Contexte : " + " ".join(morceaux) + "]"

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
        historique de conversation → vision/RAG/finance/calcul/recherche
        web/météo/automation (dans cet ordre, juste avant la question —
        voir plus bas).

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

        # Contexte de présence — matière première de la variation de ton
        # demandée par Cyril (05/08/2026). Trois signaux seulement, tous
        # déterministes (aucun LLM, CLAUDE.md règle 12) :
        #   - le mode AURA déduit de la fenêtre active (core/aura_modes.py)
        #   - depuis combien de temps ils se parlent (memory_manager)
        #   - l'heure, déjà présente dans system_context
        #
        # ⚠️ Jamais envoyé au cloud : le mode se déduit du titre de la
        # fenêtre active, qui ne sort pas de la machine (règle 3, même
        # raison que include_window=False plus haut). Un mode « Working »
        # déduit d'« impots_2025.pdf » raconte la même chose que le titre.
        presence_context = "" if is_cloud else self._describe_presence(snapshot)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": system_context},
        ]
        if presence_context:
            messages.append({"role": "system", "content": presence_context})

        # Événements système récents : ce qui s'est passé sur la machine
        # depuis le début de la session. Jamais vers le cloud — la table
        # system_events contient des extraits de contenu sensible (voir
        # voice_manager._log), qui n'ont aucune raison de sortir.
        if not is_cloud:
            # annotate_uncertain_events() rend la même forme (event_type,
            # details, date) que load_recent_events() — voir
            # core/memory_weighting.py pour ce qui change (rien tant que
            # rien n'écrit une confiance réduite ou une expiration).
            events = annotate_uncertain_events(
                self.memory.load_recent_events_with_metadata(limit=RECENT_EVENTS_IN_PROMPT)
            )
            events_context = format_events_for_prompt(events)
            if events_context:
                messages.append({"role": "system", "content": events_context})

        # Reasoning Engine (IDEAS.md #59) — désactivé par défaut, voir
        # REASONING_ENGINE_ENABLED (config.py) pour pourquoi. Même garde
        # `not is_cloud` que le RAG et les événements juste au-dessus :
        # le plan reflète la question, pas de raison de l'exclure du
        # cloud en soi, mais rester sur le même principe de contexte
        # réduit tant que ce n'est pas validé en usage réel. N'ajoute
        # jamais de réponse, seulement un bloc de contexte de plus —
        # core/reasoning_engine.py ne répond jamais à la place de
        # LucasCore.
        if not is_cloud and REASONING_ENGINE_ENABLED:
            reasoning = ReasoningEngine().plan(user_message, context)
            if reasoning.used_reasoning:
                messages.append({
                    "role": "system",
                    "content": f"Points à couvrir pour bien répondre :\n{reasoning.plan}",
                })

        # La vision est décidée AVANT de charger l'historique : quand elle
        # se déclenche, l'historique doit être raccourci (voir plus bas).
        vision_context = ""
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
                    # ⚠️ Formulation durcie le 05/08/2026. Le bloc existait
                    # déjà et s'est bien déclenché en usage réel (Cyril,
                    # « Décris ce que tu vois. » depuis la PWA), mais le
                    # modèle en a tiré : « veuillez prendre une capture
                    # d'écran » — il a inventé une manipulation manuelle au
                    # lieu de nommer les deux moyens qui existent vraiment.
                    # Le problème n'était donc pas le déclenchement mais ce
                    # que le bloc laissait ouvert : il proposait UNE issue
                    # sans interdire d'en inventer d'autres. Voir
                    # ROADMAP.md §5.31.
                    vision_context = (
                        "Cyril te parle depuis l'application mobile, pas "
                        "depuis son PC : tu N'AS PAS regardé l'écran du PC "
                        "pour cette demande, volontairement. Lire son écran "
                        "sans savoir s'il est devant serait une faute de "
                        "confidentialité, pas un détail technique.\n"
                        "Dis-le à Cyril simplement, puis propose EXACTEMENT "
                        "ces deux possibilités, sans en inventer d'autres :\n"
                        "1. le bouton caméra de l'application, pour te "
                        "montrer ce qu'il a sous les yeux ;\n"
                        "2. redemander en nommant le PC (par exemple "
                        "« regarde sur mon PC »), et tu regarderas l'écran.\n"
                        "INTERDIT : lui demander de faire lui-même une "
                        "capture d'écran, de te l'envoyer par un autre "
                        "moyen, de coller du texte, ou toute manipulation "
                        "manuelle — aucune n'est nécessaire, les deux "
                        "possibilités ci-dessus suffisent.\n"
                        "S'il parlait d'autre chose que de l'écran du PC, "
                        "réponds à ça à la place."
                    )
                    _emit(
                        on_activity, "screen_read",
                        "écran non lu — demande reçue depuis le téléphone, "
                        "sans confirmation que Cyril est devant ce PC",
                    )

        # annotate_uncertain_history() rend la même forme (role, content)
        # que load_history() — voir core/memory_weighting.py. Tout ce qui
        # suit (troncatures, filtre vision, fit_history_to_budget) opère
        # sur des tuples (role, content) ordinaires, strictement inchangé.
        history = annotate_uncertain_history(self.memory.load_history_with_metadata())
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
        # ⚠️ `not should_use_automation` : trouvé en test réel le 05/08/2026.
        # « Ouvre le bloc note » a été classé DOCUMENTS par le classifieur
        # d'intention (core/intent.py), qui a donc lancé une recherche
        # documentaire sur une demande d'ouverture d'application. Une
        # demande d'action est reconnue de façon DÉTERMINISTE, elle : quand
        # elle est certaine, elle prime sur une intention devinée. Évite
        # aussi d'injecter des extraits de documents personnels sans rapport
        # dans une réponse d'action — le « RAG qui empoisonne » que
        # CLAUDE.md décrit.
        if not is_cloud and not should_use_automation(user_message) and should_use_rag(
            user_message, context
        ):
            # ⚠️ Enveloppé depuis le 05/08/2026, après un HTTP 500 réel :
            # le modèle d'embedding (nomic-embed-text) a rendu une réponse
            # sans champ « embedding », l'exception a traversé tout
            # LucasCore.ask() et l'API a rendu 500. Résultat : Cyril
            # n'obtenait AUCUNE réponse — pas une réponse dégradée, rien.
            #
            # Une panne d'un module optionnel ne doit jamais empêcher de
            # répondre. Même principe que le `except Exception` déjà en
            # place sur le classifieur d'intention plus haut : « un doute
            # sur l'état ne doit jamais empêcher de répondre ».
            #
            # Et on ne se tait pas non plus : le bloc injecté dit que la
            # recherche a échoué, pour que le modèle ne présente pas une
            # réponse de mémoire générale comme venant des documents.
            try:
                rag_context = RAGManager().get_context(user_message)
            except Exception as exc:  # noqa: BLE001 — panne d'un module optionnel
                self.log_event("rag_unavailable", type(exc).__name__)
                _emit(on_activity, "documents_searched", "documents personnels — recherche indisponible")
                rag_context = (
                    "La recherche dans les documents personnels a ÉCHOUÉ "
                    "(service d'indexation indisponible). Tu n'as donc "
                    "consulté AUCUN document.\n"
                    "Dis-le clairement à Cyril si sa question portait sur "
                    "ses documents. INTERDIT : répondre de mémoire générale "
                    "en laissant croire que ça vient de ses documents."
                )
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

        # Finance : relevés bancaires importés en CSV (modules/finance_manager.py).
        # Jamais vers le cloud (CLAUDE.md règle 3) : un solde ou une dépense
        # nommée est une donnée ultra-sensible. is_sensitive() force déjà le
        # local sur ces mots-clés — garde redondante assumée, même
        # raisonnement que pour le RAG.
        # ⚠️ Même bug que le RAG sans résultat, même correctif : NE PAS SE
        # TAIRE. Un dossier data/finance/ vide laisserait le modèle deviner
        # un solde, indiscernable d'un vrai. Voir load_directory() pour
        # pourquoi use_llm=False ici (latence par tour de conversation).
        finance_context = ""
        if not is_cloud and should_use_finance(user_message):
            from modules.finance_manager import load_directory

            finance_manager, skipped_files = load_directory()
            if finance_manager.transactions:
                finance_context = (
                    "RELEVÉS BANCAIRES RÉELS DE CYRIL (import CSV local, jamais "
                    "envoyé au cloud) :\n\n" + finance_manager.get_summary() + "\n\n"
                    "Appuie-toi UNIQUEMENT sur ces chiffres. INTERDIT : inventer "
                    "un montant, une catégorie ou une transaction absente de ce "
                    "résumé."
                )
                if skipped_files:
                    finance_context += (
                        "\n\n⚠️ Fichier(s) ignoré(s), format illisible : "
                        + ", ".join(skipped_files)
                    )
                _emit(
                    on_activity, "finance_checked",
                    f"relevés bancaires — {len(finance_manager.transactions)} "
                    "transaction(s)",
                )
            else:
                _emit(on_activity, "finance_checked", "relevés bancaires — aucune donnée importée")
                finance_context = (
                    "RECHERCHE EFFECTUÉE DANS LES RELEVÉS BANCAIRES DE CYRIL : "
                    "AUCUNE TRANSACTION IMPORTÉE (dossier data/finance/ vide ou "
                    "absent).\n\n"
                    "Ta réponse doit dire clairement qu'aucun relevé n'a été "
                    "importé, et proposer de déposer un export CSV dans "
                    "data/finance/ pour que tu puisses l'analyser.\n"
                    "INTERDIT : citer un solde, un montant ou une catégorie de "
                    "dépense — tu n'as accès à aucune donnée financière réelle "
                    "en ce moment."
                )

        # Calculatrice (modules/calculator.py, câblé le 04/08/2026) : un LLM
        # est notoirement mauvais en arithmétique exacte — le calcul RÉEL
        # est fait ici, en Python, jamais deviné par le modèle.
        # ⚠️ Même famille de bug que le RAG/la finance sans résultat : une
        # expression qui échoue à s'évaluer doit le DIRE, pas se taire et
        # laisser le modèle inventer un chiffre plausible.
        calculation_context = ""
        if not is_cloud and should_use_calculator(user_message):
            from modules.calculator import Calculator

            expression = extract_calculation(user_message)
            result = Calculator().calculate(expression)
            if result is not None:
                calculation_context = (
                    f"CALCUL RÉEL EFFECTUÉ : {expression} = {result}\n\n"
                    "Utilise EXACTEMENT ce résultat. INTERDIT : recalculer, "
                    "arrondir différemment, ou corriger ce nombre — même s'il "
                    "te semble étrange, c'est le résultat réel."
                )
                _emit(on_activity, "calculated", f"calcul — {expression} = {result}")
            else:
                calculation_context = (
                    f"UNE EXPRESSION A ÉTÉ DÉTECTÉE ({expression!r}) MAIS N'A "
                    "PAS PU ÊTRE ÉVALUÉE (syntaxe invalide ou division par "
                    "zéro).\n\nDis-le à Cyril plutôt que d'inventer un résultat."
                )
                _emit(on_activity, "calculated", f"calcul — expression invalide ({expression})")

        # Recherche web (modules/web_search.py, câblé le 04/08/2026).
        # Déclenchement volontairement étroit (voir should_use_websearch) :
        # chaque requête part chez DuckDuckGo, la troisième surface par
        # laquelle du texte quitte la machine (après le LLM cloud et
        # edge_tts) — le filtre anti-fuite de WebSearch.search() refuse déjà
        # toute donnée identifiante AVANT l'appel réseau.
        websearch_context = ""
        if not is_cloud and should_use_websearch(user_message):
            from modules.web_search import WebSearch

            # ⚠️ Corrigé le 05/08/2026 (audit « silence qui laisse le modèle
            # deviner », ROADMAP.md §5.39). Avant : les QUATRE issues
            # possibles — résultats, zéro résultat, panne réseau, refus pour
            # donnée identifiante — étaient injectées sous la même étiquette
            # « RECHERCHE WEB RÉELLE » suivie de « appuie-toi uniquement sur
            # ces résultats réels ».
            #
            # Un refus de confidentialité arrivait donc au modèle présenté
            # comme de vrais résultats de recherche, avec l'ordre de s'en
            # servir. Ce n'est pas un silence, c'est une étiquette fausse —
            # plus trompeur encore, parce que rien n'invite à s'en méfier.
            summary, issue = WebSearch(
                log_event=self.log_event
            ).get_summary_with_outcome(user_message)

            if issue == "ok":
                websearch_context = (
                    "RECHERCHE WEB RÉELLE (DuckDuckGo) :\n\n" + summary + "\n\n"
                    "Appuie-toi UNIQUEMENT sur ces résultats réels. INTERDIT : "
                    "inventer un résultat, un lien ou un fait absent de cette "
                    "recherche."
                )
                _emit(on_activity, "websearch_performed", "recherche web — résultats reçus")
            elif issue == "empty":
                websearch_context = (
                    "RECHERCHE WEB EFFECTUÉE : AUCUN RÉSULTAT.\n\n"
                    "Dis-le à Cyril. INTERDIT : inventer un résultat, un lien "
                    "ou un fait — tu n'as rien trouvé."
                )
                _emit(on_activity, "websearch_performed", "recherche web — aucun résultat")
            elif issue == "refused":
                websearch_context = (
                    "RECHERCHE WEB REFUSÉE : la question contenait une donnée "
                    "personnelle identifiante, elle n'a donc JAMAIS été envoyée "
                    "sur Internet.\n\n"
                    "Explique-le à Cyril — c'est une protection volontaire, pas "
                    "une panne. Propose-lui de reformuler sans la donnée "
                    "personnelle. INTERDIT : prétendre avoir cherché, ou "
                    "inventer un résultat."
                )
                _emit(on_activity, "websearch_performed", "recherche web — refusée (donnée personnelle)")
            else:  # "failed"
                websearch_context = (
                    "LA RECHERCHE WEB A ÉCHOUÉ (réseau ou service "
                    "indisponible). Tu n'as AUCUN résultat.\n\n"
                    "Dis-le à Cyril. INTERDIT : répondre de mémoire générale "
                    "en laissant croire que ça vient d'une recherche."
                )
                _emit(on_activity, "websearch_performed", "recherche web — échec")

        # Météo (modules/weather_manager.py, câblé le 04/08/2026). Jamais
        # deviner une ville absente de la question — même principe que le
        # RAG/la finance sans résultat : demander plutôt qu'inventer.
        weather_context = ""
        if not is_cloud and should_use_weather(user_message):
            city = extract_city(user_message)
            if city is None:
                weather_context = (
                    "MÉTÉO DEMANDÉE MAIS AUCUNE VILLE NOMMÉE DANS LA QUESTION.\n\n"
                    "Demande à Cyril de préciser la ville — ne devine JAMAIS "
                    "laquelle, même s'il en a mentionné une plus tôt dans la "
                    "conversation."
                )
                _emit(on_activity, "weather_checked", "météo — aucune ville nommée")
            else:
                from modules.weather_manager import WeatherManager

                weather = WeatherManager()
                data = weather.get_current(city)
                if data is not None:
                    weather_context = (
                        f"MÉTÉO RÉELLE (wttr.in) : {weather.format_for_display(data)}\n\n"
                        "Utilise UNIQUEMENT ces données réelles. INTERDIT : inventer "
                        "une température, une condition ou changer ces chiffres."
                    )
                    _emit(on_activity, "weather_checked", f"météo — {city}")
                else:
                    weather_context = (
                        f"MÉTÉO DEMANDÉE POUR « {city} » MAIS INDISPONIBLE (ville "
                        "invalide ou service injoignable).\n\n"
                        "Dis-le clairement à Cyril. INTERDIT : inventer une "
                        "température ou une condition météo."
                    )
                    _emit(on_activity, "weather_checked", f"météo — {city} indisponible")

        # Automation (modules/automation_manager.py, PREMIER câblage réel de
        # core/decision_engine.py, accord explicite de Cyril, 04/08/2026 —
        # voir ROADMAP.md §5.25). Contrairement aux blocs ci-dessus, celui-ci
        # a un VRAI effet de bord (lance un process) — pas seulement du
        # contexte injecté pour le LLM.
        #
        # ⚠️ `confirm=lambda spec: True` est un choix EXPLICITE et TEMPORAIRE,
        # pas un oubli : Cyril demande explicitement de garder le
        # comportement actuel (aucune confirmation) pour cette migration —
        # la confirmation UI viendra avec les cartes d'approbation
        # (IDEAS.md #80), chantier distinct. `ActionCategory.EXECUTE` exige
        # structurellement une confirmation (core/decision_engine.py) ; ce
        # callable en tient lieu, en attendant une vraie UI.
        #
        # ⚠️ Le journal (action_log) est écrit ICI, explicitement, PAS via
        # le `log_event` interne de DecisionEngine : `_require()` lève
        # `ActionDenied` directement pour une action inconnue de la liste
        # blanche, sans jamais appeler `self._log(...)` — seul le refus de
        # CONFIRMATION passe par ce chemin interne. Écrire le journal ici,
        # dans les deux branches (succès/refus), garantit qu'une action
        # hors liste blanche est journalisée comme refus quel que soit
        # l'endroit précis où `ActionDenied` a été levée à l'intérieur de
        # `core/decision_engine.py` — trouvé en écrivant le test de refus.
        automation_context = ""
        # Remis à False à CHAQUE construction : c'est le témoin qui autorise
        # (ou non) la réponse à affirmer qu'une action a eu lieu, relu dans
        # ask(). Un témoin qui resterait vrai d'un tour sur l'autre
        # rouvrirait exactement la faille qu'il ferme.
        self._action_executed = False
        if not is_cloud and should_use_automation(user_message):
            from core.decision_engine import (
                ActionDenied,
                DecisionEngine,
                automation_manager_actions,
            )
            from modules.automation_manager import AutomationManager

            app_name = extract_app_name(user_message)
            action_name = f"launch_{app_name}"
            engine = DecisionEngine(confirm=lambda spec: True)
            for spec in automation_manager_actions():
                engine.register(spec)

            automation = AutomationManager(log_event=self.log_event)
            try:
                result_message = engine.request(action_name, run=lambda: automation.open_app(app_name))
                self.memory.save_action(action=action_name, source="chat", result="executed")
                self._action_executed = True
                automation_context = (
                    f"ACTION RÉELLE EFFECTUÉE : {result_message}\n\n"
                    "Confirme ceci à Cyril. INTERDIT : prétendre avoir fait "
                    "autre chose, ou inventer un résultat différent."
                )
                _emit(on_activity, "automation_requested", f"lancement — {app_name}")
            except ActionDenied as exc:
                self.memory.save_action(action=action_name, source="chat", result="denied")
                automation_context = (
                    f"ACTION REFUSÉE : {exc}\n\n"
                    "Dis-le clairement à Cyril plutôt que de prétendre avoir "
                    "lancé l'application."
                )
                _emit(on_activity, "automation_requested", f"lancement refusé — {app_name}")
        elif not is_cloud and looks_like_app_request(user_message):
            # ⚠️ LE TROU QUI A PRODUIT LA FAUSSE CONFIRMATION (05/08/2026).
            #
            # Cyril a écrit « ouvre le bloc note » (singulier) : aucun alias
            # ne correspondait, donc `should_use_automation` était faux, donc
            # AUCUN bloc de contexte n'était injecté — ni succès, ni refus.
            # Le modèle n'avait donc aucune information sur l'action, et a
            # répondu « Le Bloc-notes est lancé » alors que rien ne s'était
            # ouvert, ni même tenté (`action_log` vide pour ce tour).
            #
            # Le silence était le bug. Une demande d'action non exécutée doit
            # produire un contexte EXPLICITE, exactement comme un RAG sans
            # résultat ou une capture d'écran refusée plus haut : le modèle
            # ne doit jamais avoir à deviner ce qui s'est passé sur la
            # machine de Cyril. Voir ROADMAP.md §5.31.
            from modules.automation_manager import WHITELISTED_APPS

            disponibles = ", ".join(sorted(WHITELISTED_APPS))
            automation_context = (
                "Cyril semble demander d'ouvrir une application, mais aucune "
                "application connue n'a été reconnue dans sa phrase.\n"
                "AUCUNE ACTION N'A ÉTÉ EFFECTUÉE : rien n'a été lancé, rien "
                "n'a même été tenté.\n"
                "INTERDIT ABSOLU : écrire qu'une application est lancée, "
                "ouverte, démarrée, ou que tu vas l'ouvrir. Ce serait faux.\n"
                f"Dis-lui que tu n'as pas reconnu l'application, et rappelle "
                f"celles que tu sais ouvrir : {disponibles}."
            )
            _emit(on_activity, "automation_requested", "action demandée — application non reconnue")

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
        # ajoutée ici devra passer par ce même plafond — la finance y
        # compris (03/08/2026) : même bloc, même risque de noyade.
        if not is_cloud and (
            vision_context or rag_context or finance_context
            or calculation_context or websearch_context or weather_context
            or automation_context
        ):
            history = history[-SOURCE_HISTORY_MESSAGES:]

        # ⚠️ AUTO-IMITATION DE REFUS DE VISION — trouvé en conditions
        # réelles le 03/08/2026 (screenshot + vraie base à l'appui, voir
        # real_vision_test*.py de la session précédente) : qwen2.5:7b
        # répond "je n'ai pas accès à l'écran" malgré une consigne
        # explicite contraire dans vision_context ("Ne dis JAMAIS que tu
        # ne peux pas voir l'écran : tu viens de le faire"), parce que
        # les tours d'historique juste avant sont des refus identiques
        # répétés — le modèle imite le motif qu'il vient de produire
        # plutôt que la consigne qui le contredit.
        #
        # Ne filtre QUE les réponses de l'ASSISTANT (les questions de
        # Cyril restent intactes — "Décris ce que tu vois" répété trois
        # fois n'est pas le problème, c'est la réponse qui l'est), et
        # UNIQUEMENT quand un nouveau bloc vision va réellement être
        # injecté pour CE tour — aucun effet sur le RAG, la finance ou
        # une conversation qui ne déclenche pas la vision.
        if not is_cloud and vision_context:
            history = [
                (role, content) for role, content in history
                if not (role == "assistant" and is_vision_refusal(content))
            ]

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

        if finance_context:
            messages.append({"role": "system", "content": finance_context})

        if calculation_context:
            messages.append({"role": "system", "content": calculation_context})

        if websearch_context:
            messages.append({"role": "system", "content": websearch_context})

        if weather_context:
            messages.append({"role": "system", "content": weather_context})

        if automation_context:
            messages.append({"role": "system", "content": automation_context})

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
        # ⚠️ Ici et pas dans _build_messages : celui-ci est aussi appelé par
        # build_messages_for_ui() pour un simple APERÇU du prompt. Y placer
        # la commande ferait basculer le mode Deep Focus sans que Cyril ait
        # rien envoyé — un effet de bord déclenché par un affichage.
        self.aura.handle_command(user_message)
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

        # Garde-fou déterministe — voir claims_action_success() plus haut.
        # Placé APRÈS la génération et AVANT l'enregistrement en mémoire :
        # une fausse confirmation non corrigée en base deviendrait un
        # exemple à imiter au tour suivant (§5.5, auto-imitation).
        if not getattr(self, "_action_executed", False) and claims_action_success(answer):
            answer = answer.rstrip() + FALSE_CLAIM_CORRECTION
            self.memory.save_action(
                action="unknown", source="chat", result="false_claim_corrected"
            )
            _emit(
                on_activity, "automation_requested",
                "fausse confirmation corrigée — aucune action réelle",
            )

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
