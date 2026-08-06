# core/aura_modes.py — détection du mode AURA actif
#
# ⚠️ MVP RÉDUIT (session autonome 04/08/2026), 2 modes sur les 8 catalogués
# dans IDEAS.md §3 ("Les 8 Modes AURA") : Working et Deep Focus — les deux
# les moins ambigus à détecter sans un LLM. Les 6 autres (Creating,
# Meeting, Gaming, Entertainment, Learning, Social) suivent le même patron
# (une liste de déclencheurs -> un AuraMode) mais ne sont volontairement
# PAS construits ici : chacun mérite sa propre liste d'apps/mots-clés
# vérifiée avec Cyril, pas une extrapolation en session autonome.
#
# Ce module détecte le mode, POINT. Les "comportements" de la table
# IDEAS.md (notifications filtrées, musique lo-fi, compte à rebours...)
# sont de vraies actions système qui n'existent pas encore dans le
# projet et ne sont pas construites ici — même prudence que
# core/decision_engine.py : détecter n'est pas agir.
#
# Déterministe, comme core/router.py : du code Python qui décide, jamais
# un LLM (CLAUDE.md règle 12).

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from core.text_utils import normalize


class AuraMode(Enum):
    NONE = "none"
    WORKING = "working"
    DEEP_FOCUS = "deep_focus"
    CREATING = "creating"
    MEETING = "meeting"
    GAMING = "gaming"
    ENTERTAINMENT = "entertainment"
    LEARNING = "learning"
    SOCIAL = "social"


# Reconnus par leur présence dans le titre de la fenêtre active
# (core/world_model.py::get_snapshot()["active_window"]) — pas une liste
# exhaustive, un point de départ vérifiable et extensible.
#
# ⚠️ Bug réel trouvé le 04/08/2026 (audit "validation contre le vrai
# service" étendu aux modes AURA) : "excel", "word" et "terminal" en
# sous-chaîne nue déclenchaient WORKING sur des titres de fenêtre réels
# et courants sans aucun rapport avec du travail — « Wordle - The New
# York Times », « Word Search Puzzle », « Terminal illness support
# group »… Les vrais titres Office se terminent de façon stable par
# « - Excel »/« - Word » (mêmes fenêtres testées : « Classeur1 - Excel »,
# « Document1 - Word ») — même technique de désambiguïsation que
# « - code » déjà en place pour Visual Studio Code. « terminal » nu est
# retiré : "powershell"/"command prompt" couvrent déjà les cas réels
# usuels, "windows terminal" ajouté pour l'appli moderne du même nom.
WORKING_APP_MARKERS = (
    "visual studio code", " - code", "pycharm", " - excel", " - word",
    "powerpoint", "outlook", "windows terminal", "powershell",
    "command prompt", "notepad++",
)

# ⚠️ Ajouté le 05/08/2026 après vérification sur la machine réelle : le
# terminal de Cyril s'intitulait « ⠐ Valider avatar Godot et relancer
# serveur API ». Le marqueur de titre « windows terminal » ne pouvait donc
# pas le voir — un terminal affiche ce que l'utilisateur y écrit, pas son
# propre nom. C'est le cas d'usage qui a justifié `active_process`.
WORKING_PROCESSES = (
    "windowsterminal", "code", "pycharm64", "excel", "winword", "powerpnt",
    "outlook", "powershell", "pwsh", "cmd", "notepad++",
)

# ── Les 6 modes restants (05/08/2026, demande explicite de Cyril) ──────
#
# Le commentaire d'en-tête de ce module disait que ces 6 modes ne seraient
# pas construits en session autonome, « chacun méritant sa propre liste
# vérifiée avec Cyril ». Cyril a levé cette réserve explicitement dans
# l'instruction du 05/08/2026. Ce qui reste verrouillé, en revanche, et
# qu'il a re-verrouillé lui-même : un mode ne donne droit qu'à un TON
# différent, jamais à une action système.
#
# ⚠️ Deux sources, pas une — et c'est ce qui rend la détection utilisable :
#   - le TITRE de la fenêtre, seul moyen d'atteindre ce qui vit dans un
#     navigateur (YouTube, Netflix, une doc) où le process vaut « chrome » ;
#   - le NOM DU PROCESS, stable quoi que l'utilisateur écrive dans son
#     titre — le terminal de cette machine s'appelait « ⠐ Valider avatar
#     Godot et relancer serveur API », qu'aucun marqueur de titre
#     n'attrapera jamais.
#
# ⚠️ Marqueurs volontairement SPÉCIFIQUES, leçon du 04/08/2026 : « excel »
# en sous-chaîne nue déclenchait WORKING sur « Wordle - The New York
# Times ». Un mot court et courant coûte plus cher qu'un mot manquant, ici
# comme là-bas.
#
# Les process sont comparés en ÉGALITÉ, pas en sous-chaîne : « steam » ne
# doit pas correspondre à « steamwebhelper », qui tourne en permanence dès
# que Steam est ouvert, même quand Cyril ne joue pas.

CREATING_TITLE_MARKERS = (
    "photoshop", "illustrator", "premiere pro", "after effects", "davinci resolve",
    "blender", "figma", "inkscape", "krita", "audacity", "ableton", "fl studio",
    "affinity photo", "affinity designer",
)
CREATING_PROCESSES = (
    "photoshop", "illustrator", "adobe premiere pro", "afterfx", "resolve",
    "blender", "figma", "gimp", "inkscape", "krita", "audacity", "ableton live",
    "obs64", "obs32",
)

MEETING_TITLE_MARKERS = (
    "microsoft teams", "zoom meeting", "google meet", "meet.google.com",
    "webex", "reunion en cours", "whereby",
)
MEETING_PROCESSES = ("teams", "ms-teams", "zoom", "webex", "webexmta")

GAMING_TITLE_MARKERS = (
    "steam", "epic games launcher", "battle.net", "riot client", "gog galaxy",
    "minecraft", "counter-strike", "league of legends", "valorant", "fortnite",
    "cyberpunk 2077", "elden ring", "rocket league",
)
GAMING_PROCESSES = (
    "steam", "epicgameslauncher", "battle.net", "riotclientux", "galaxyclient",
    "javaw", "cs2", "valorant", "leagueoflegends", "rocketleague",
)

ENTERTAINMENT_TITLE_MARKERS = (
    "netflix", "youtube", "twitch", "prime video", "disney+", "canal+",
    "spotify", "deezer", "molotov", "arte.tv",
)
ENTERTAINMENT_PROCESSES = ("spotify", "vlc", "netflix", "mpc-hc64")

LEARNING_TITLE_MARKERS = (
    "udemy", "coursera", "openclassrooms", "khan academy", "stack overflow",
    "wikipedia", "documentation", "docs.python", "developer.mozilla",
    "tutoriel", "tutorial", "how to ", "comment faire",
)
LEARNING_PROCESSES = ()

SOCIAL_TITLE_MARKERS = (
    "whatsapp", "messenger", "instagram", "facebook", "linkedin", "reddit",
    "tiktok", "telegram", "signal", "mastodon", "bluesky", " / x", "twitter",
)
SOCIAL_PROCESSES = ("whatsapp", "discord", "telegram", "signal", "slack")

# ⚠️ YouTube est le seul cas vraiment ambigu, et il est fréquent : la même
# plateforme sert un clip et un cours. Ces marqueurs, trouvés DANS le titre
# d'une page YouTube, le basculent vers LEARNING plutôt que ENTERTAINMENT.
# Ailleurs, la précédence ci-dessous suffit.
LEARNING_OVERRIDE_MARKERS = ("tutoriel", "tutorial", "how to ", "cours ", "apprendre")

# ── Précédence ────────────────────────────────────────────────────────
#
# Deux modes peuvent correspondre en même temps (un Discord ouvert
# par-dessus un jeu, une doc dans un onglet à côté d'une visio). L'ordre
# ci-dessous tranche, et il est explicite plutôt que laissé au hasard de
# l'ordre d'écriture :
#
#   1. MEETING       — quelqu'un attend en face ; le plus coûteux à ignorer
#   2. GAMING        — plein écran, interrompre est le plus intrusif
#   3. CREATING      — état de concentration fragile
#   4. WORKING       — le défaut professionnel, déjà en place
#   5. LEARNING      — attention soutenue, mais interruptible
#   6. SOCIAL        — déjà dans l'échange
#   7. ENTERTAINMENT — le plus interruptible, donc le dernier
#
# DEEP_FOCUS reste au-dessus de tout : il vient d'une commande explicite de
# Cyril, jamais d'une déduction. Une fenêtre ne doit pas pouvoir annuler
# silencieusement une demande de concentration.
_DETECTION_ORDER: tuple[tuple[AuraMode, tuple[str, ...], tuple[str, ...]], ...] = (
    (AuraMode.MEETING, MEETING_TITLE_MARKERS, MEETING_PROCESSES),
    (AuraMode.GAMING, GAMING_TITLE_MARKERS, GAMING_PROCESSES),
    (AuraMode.CREATING, CREATING_TITLE_MARKERS, CREATING_PROCESSES),
    (AuraMode.WORKING, WORKING_APP_MARKERS, WORKING_PROCESSES),
    (AuraMode.LEARNING, LEARNING_TITLE_MARKERS, LEARNING_PROCESSES),
    (AuraMode.SOCIAL, SOCIAL_TITLE_MARKERS, SOCIAL_PROCESSES),
    (AuraMode.ENTERTAINMENT, ENTERTAINMENT_TITLE_MARKERS, ENTERTAINMENT_PROCESSES),
)

# Déclenchement EXPLICITE uniquement, jamais deviné depuis l'écran :
# bloquer les notifications sur une inférence fragile serait pire que ne
# rien bloquer du tout. Comparé sur une phrase en minuscules, en
# sous-chaîne — assez large pour couvrir des formulations proches, testé
# sur un corpus comme test_intent.py.
#
# ⚠️ Comparées après core.text_utils.normalize(), jamais avec .lower()
# seul. Bug réel trouvé le 05/08/2026 en câblant le moteur : « desactive
# le mode focus » tapé SANS ACCENT ne correspondait à aucune phrase OFF —
# mais contient littéralement la sous-chaîne « active le mode focus », donc
# il tombait dans la branche ON. Taper vite inversait le sens de la
# commande : demander l'arrêt de la concentration l'activait.
#
# C'est exactement la raison d'être de core/text_utils.py (« Toute
# comparaison de mots-clés doit passer par normalize() ») ; ce module avait
# été écrit sans, et personne ne l'avait vu parce que rien ne l'appelait.
# Les phrases ci-dessous sont donc écrites DÉJÀ normalisées (sans accent),
# et normalize() est appliqué à l'entrée.
DEEP_FOCUS_ON_PHRASES = (
    "active le mode focus", "active le mode deep focus", "mode deep focus",
    "concentre-toi", "concentre toi", "mode concentration",
)
DEEP_FOCUS_OFF_PHRASES = (
    "desactive le mode focus", "arrete le mode focus", "sors du mode focus",
    "fin du focus", "fin de la concentration", "stop le mode focus",
)


@dataclass(frozen=True)
class AuraModeChange:
    """Résultat d'une commande qui a changé le mode — None si la phrase n'en concernait aucun."""

    mode: AuraMode
    reason: str


# Ce que chaque mode change dans le TON de Luca — et rien d'autre.
#
# ⚠️ Périmètre verrouillé (instruction de Cyril, 05/08/2026) : les
# "comportements" de la table IDEAS.md §3 (filtrer les notifications,
# lancer une musique, fermer des onglets, régler le volume) sont de
# VRAIES actions système. Chacune serait une entrée de plus dans la liste
# blanche de core/decision_engine.py, et personne n'a validé d'en ajouter
# — une seule existe à ce jour, le lancement d'application. Détecter un
# mode ne donne donc le droit qu'à une chose : parler différemment.
#
# Formulé comme une consigne courte et concrète : un ton décrit en
# abstrait ("sois plus efficace") ne change rien à une génération.
MODE_TONE_HINTS: dict[AuraMode, str] = {
    AuraMode.WORKING: (
        "Cyril travaille. Va droit au but, pas de digression ni de relance."
    ),
    AuraMode.DEEP_FOCUS: (
        "Cyril est en concentration profonde. Réponds en une ou deux phrases "
        "maximum, sans aucune question de relance."
    ),
    AuraMode.MEETING: (
        "Cyril est en réunion ou en visio. Réponds très brièvement : "
        "quelqu'un attend en face de lui."
    ),
    AuraMode.GAMING: (
        "Cyril joue. Réponse courte, il est en plein écran et ne peut pas "
        "lire un pavé."
    ),
    AuraMode.CREATING: (
        "Cyril est dans un travail créatif. Reste concis et ne romps pas sa "
        "concentration ; s'il cherche des idées, propose-les franchement."
    ),
    AuraMode.LEARNING: (
        "Cyril est en train d'apprendre quelque chose. Explique pas à pas et "
        "sans raccourci, c'est le moment où le détail sert."
    ),
    AuraMode.SOCIAL: (
        "Cyril est dans ses messages. Réponds court, il fait autre chose en "
        "parallèle."
    ),
    AuraMode.ENTERTAINMENT: (
        "Cyril se détend. Ton léger, réponse brève, aucune relance de travail."
    ),
}


def tone_hint(mode: AuraMode) -> str:
    """Consigne de ton associée à un mode — chaîne vide si aucune."""
    return MODE_TONE_HINTS.get(mode, "")


class AuraModeEngine:
    """
    Détecte le mode AURA actif.

    Deep Focus est le seul mode "collant" : activé par une commande
    explicite, il reste actif jusqu'à désactivation explicite, quelle
    que soit la fenêtre ensuite au premier plan — jamais une fenêtre qui
    annule silencieusement une demande de concentration. Working, lui,
    se déduit à chaque appel depuis la fenêtre active, sans mémoire.

    ⚠️ `store` (05/08/2026, premier câblage réel) : sans lui, ce moteur ne
    fonctionnait pas du tout en conditions réelles. `LucasCore` est recréé
    à CHAQUE requête (contrainte SQLite/threads, api/server.py), donc
    `_deep_focus_active` gardé en mémoire vive repartait à False au message
    suivant — un mode "collant" qui se décollait tout seul. `store` est un
    couple (lire, écrire) fourni par l'appelant : le moteur reste ignorant
    de SQLite, comme `log_event` ailleurs dans le projet. Sans `store`, le
    comportement en mémoire d'origine est conservé (utile pour les tests).
    """

    _STATE_KEY = "aura_deep_focus"

    def __init__(self, store: tuple[Callable[[], str | None], Callable[[str], None]] | None = None) -> None:
        # Annotations explicites : le déballage d'un `tuple | None` avec un
        # repli `(None, None)` ne donne à mypy aucun type déductible pour
        # les deux attributs. Les nommer dit ce que la classe accepte —
        # soit les deux fonctions de stockage, soit aucune.
        self._read: Callable[[], str | None] | None
        self._write: Callable[[str], None] | None
        self._read, self._write = store if store else (None, None)
        self._deep_focus_active = False
        if self._read is not None:
            self._deep_focus_active = self._read() == "1"

    def _set_deep_focus(self, actif: bool) -> None:
        self._deep_focus_active = actif
        if self._write is not None:
            self._write("1" if actif else "0")

    def handle_command(self, text: str) -> AuraModeChange | None:
        """
        Active/désactive Deep Focus si `text` le demande explicitement.
        None sinon.

        ⚠️ OFF vérifié AVANT ON : « désactive le mode focus » contient
        littéralement la sous-chaîne « active le mode focus » — sans cet
        ordre, une désactivation serait lue comme une activation.
        """
        lowered = normalize(text)
        if any(phrase in lowered for phrase in DEEP_FOCUS_OFF_PHRASES):
            self._set_deep_focus(False)
            return AuraModeChange(AuraMode.NONE, "commande explicite")
        if any(phrase in lowered for phrase in DEEP_FOCUS_ON_PHRASES):
            self._set_deep_focus(True)
            return AuraModeChange(AuraMode.DEEP_FOCUS, "commande explicite")
        return None

    def detect(self, active_window: str, active_process: str = "") -> AuraMode:
        """
        Mode actuellement actif.

        `active_process` est optionnel et vaut "" par défaut : les appelants
        qui n'ont que le titre (tests historiques, snapshots anciens)
        continuent de fonctionner exactement comme avant.
        """
        if self._deep_focus_active:
            return AuraMode.DEEP_FOCUS

        # Normalisé comme les commandes : un titre de fenêtre accentué
        # (« Résumé - Word ») doit se comparer sur le même terrain.
        titre = normalize(active_window or "")
        process = normalize(active_process or "")

        for mode, marqueurs_titre, processus in _DETECTION_ORDER:
            par_titre = any(marqueur in titre for marqueur in marqueurs_titre)
            # Égalité, pas sous-chaîne : « steam » ne doit pas correspondre
            # à « steamwebhelper », qui tourne dès que Steam est lancé —
            # y compris quand Cyril ne joue pas du tout.
            par_process = process != "" and process in processus
            if not (par_titre or par_process):
                continue

            # YouTube sert autant un cours qu'un clip : le titre tranche.
            if mode is AuraMode.ENTERTAINMENT and any(
                marqueur in titre for marqueur in LEARNING_OVERRIDE_MARKERS
            ):
                return AuraMode.LEARNING
            return mode

        return AuraMode.NONE
