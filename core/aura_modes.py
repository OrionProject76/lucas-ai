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

    def detect(self, active_window: str) -> AuraMode:
        """Mode actuellement actif, Deep Focus prévalant toujours sur Working."""
        if self._deep_focus_active:
            return AuraMode.DEEP_FOCUS

        # Normalisé comme les commandes : un titre de fenêtre accentué
        # (« Résumé - Word ») doit se comparer sur le même terrain.
        lowered = normalize(active_window or "")
        if any(marker in lowered for marker in WORKING_APP_MARKERS):
            return AuraMode.WORKING

        return AuraMode.NONE
