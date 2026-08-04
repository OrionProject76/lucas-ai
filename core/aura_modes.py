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

from dataclasses import dataclass
from enum import Enum


class AuraMode(Enum):
    NONE = "none"
    WORKING = "working"
    DEEP_FOCUS = "deep_focus"


# Reconnus par leur présence dans le titre de la fenêtre active
# (core/world_model.py::get_snapshot()["active_window"]) — pas une liste
# exhaustive, un point de départ vérifiable et extensible.
WORKING_APP_MARKERS = (
    "visual studio code", " - code", "pycharm", "excel", "word",
    "powerpoint", "outlook", "terminal", "powershell",
    "command prompt", "notepad++",
)

# Déclenchement EXPLICITE uniquement, jamais deviné depuis l'écran :
# bloquer les notifications sur une inférence fragile serait pire que ne
# rien bloquer du tout. Comparé sur une phrase en minuscules, en
# sous-chaîne — assez large pour couvrir des formulations proches, testé
# sur un corpus comme test_intent.py.
DEEP_FOCUS_ON_PHRASES = (
    "active le mode focus", "active le mode deep focus", "mode deep focus",
    "concentre-toi", "mode concentration",
)
DEEP_FOCUS_OFF_PHRASES = (
    "désactive le mode focus", "arrête le mode focus", "sors du mode focus",
    "fin du focus", "fin de la concentration",
)


@dataclass(frozen=True)
class AuraModeChange:
    """Résultat d'une commande qui a changé le mode — None si la phrase n'en concernait aucun."""

    mode: AuraMode
    reason: str


class AuraModeEngine:
    """
    Détecte le mode AURA actif.

    Deep Focus est le seul mode "collant" : activé par une commande
    explicite, il reste actif jusqu'à désactivation explicite, quelle
    que soit la fenêtre ensuite au premier plan — jamais une fenêtre qui
    annule silencieusement une demande de concentration. Working, lui,
    se déduit à chaque appel depuis la fenêtre active, sans mémoire.
    """

    def __init__(self) -> None:
        self._deep_focus_active = False

    def handle_command(self, text: str) -> AuraModeChange | None:
        """
        Active/désactive Deep Focus si `text` le demande explicitement.
        None sinon.

        ⚠️ OFF vérifié AVANT ON : « désactive le mode focus » contient
        littéralement la sous-chaîne « active le mode focus » — sans cet
        ordre, une désactivation serait lue comme une activation.
        """
        lowered = text.lower()
        if any(phrase in lowered for phrase in DEEP_FOCUS_OFF_PHRASES):
            self._deep_focus_active = False
            return AuraModeChange(AuraMode.NONE, "commande explicite")
        if any(phrase in lowered for phrase in DEEP_FOCUS_ON_PHRASES):
            self._deep_focus_active = True
            return AuraModeChange(AuraMode.DEEP_FOCUS, "commande explicite")
        return None

    def detect(self, active_window: str) -> AuraMode:
        """Mode actuellement actif, Deep Focus prévalant toujours sur Working."""
        if self._deep_focus_active:
            return AuraMode.DEEP_FOCUS

        lowered = (active_window or "").lower()
        if any(marker in lowered for marker in WORKING_APP_MARKERS):
            return AuraMode.WORKING

        return AuraMode.NONE
