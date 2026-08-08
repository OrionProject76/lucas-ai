# core/decision_engine.py — qui peut agir sans demander, qui doit demander avant
#
# ⚠️ Construit et testé le 04/08/2026 (session autonome), mais RIEN n'est
# câblé dessus au-delà de ce qui existe déjà. modules/automation_manager.py
# (lancement d'appli sur liste blanche, sans confirmation) reste inchangé,
# et Semantic Desktop reste lecture seule. Le premier vrai branchement
# d'une action réelle sur ce moteur est une décision de sécurité — voir
# CLAUDE.md, "Autonomie d'exécution", cas 1 — à valider avec Cyril en
# direct, pas en session autonome.
#
# Doctrine de référence : VISION_LONG_TERME.md §4 — « Luca's a un accès
# large et réel à ce dont elle a besoin... mais dès qu'il y a un doute ou
# un risque réel sur une action, elle soumet une requête explicite à
# Cyril, qui valide ou refuse ». Ce module est la structure qui porte
# cette règle, pas une nouvelle liste d'actions à exécuter.
#
# Les cartes d'approbation UI (IDEAS.md #80) et STOP mid-tool-call (#81)
# viendront se brancher sur `confirm` plus tard — ce module ne les
# suppose pas, `confirm` est un simple callable injectable, comme
# `log_event` ailleurs dans le projet (security/, automation_manager).

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class ActionCategory(Enum):
    """
    Trois natures de CONSÉQUENCE, pas trois natures technique d'action.

    READ    : n'altère rien — lire l'état d'un paramètre ou d'un capteur.
              Jamais de confirmation : un risque réel suppose un effet.
    WRITE   : modifie un paramètre système réversible (volume, luminosité,
              contenu du presse-papier). Confirmation exigée.
    EXECUTE : lance un programme ou produit un effet externe (ouvrir une
              appli, capturer l'écran, écrire un fichier). Confirmation
              exigée, ET journalisé — un effet externe laisse une trace,
              une lecture ou un réglage n'en a pas besoin.
    """

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"


CONFIRMATION_REQUIRED = frozenset({ActionCategory.WRITE, ActionCategory.EXECUTE})
LOGGED_CATEGORIES = frozenset({ActionCategory.EXECUTE})


class ActionDenied(Exception):
    """
    L'action n'a pas pu s'exécuter — refusée explicitement, inconnue de la
    liste blanche, ou confirmation exigée mais indisponible.

    Toujours une exception, jamais une valeur "refusé" retournée en
    silence : un appelant qui oublie de vérifier ne doit pas pouvoir
    croire qu'une action a eu lieu alors qu'elle a été bloquée.
    """


@dataclass(frozen=True)
class ActionSpec:
    """
    Description déclarative d'une action de la liste blanche.

    Ce n'est PAS l'action elle-même : `run` (un callable) est fourni au
    moment de l'appel à `request()`, jamais stocké ici — ActionSpec reste
    un objet de donnée pur, montrable tel quel à une future carte
    d'approbation (nom + description), sans référence à du code exécutable.
    """

    name: str
    category: ActionCategory
    description: str = ""


# ── RÉEL : dérivé de la seule liste blanche qui existe et tourne ────────
#
# ⚠️ Trouvé le 04/08/2026 (session autonome) : aucune liste blanche
# catégorisée n'existait avant ce module — recherche faite dans
# IDEAS.md/VISION_LONG_TERME.md/ROADMAP.md, aucune trace. Le SEUL
# mécanisme réel, avant comme après, est modules/automation_manager.py
# (lancement d'appli, sans confirmation). Voir CLAUDE.md, "Précision :
# la liste blanche... reflète l'existant" et ROADMAP.md §5.15.


def automation_manager_actions() -> tuple[ActionSpec, ...]:
    """
    ActionSpec réels, un par application de
    modules.automation_manager.WHITELISTED_APPS — générés à CHAQUE APPEL,
    jamais recopiés à la main : une copie figée aurait dérivé au premier
    ajout ou retrait d'application dans automation_manager.py, exactement
    le problème que ce module corrige.

    Tous EXECUTE : lancer une application produit un effet externe réel.
    Aucun n'est enregistré automatiquement dans un DecisionEngine, et
    modules/automation_manager.py n'appelle jamais ce module — toujours
    aucune confirmation avant de lancer une appli aujourd'hui.
    """
    from modules.automation_manager import WHITELISTED_APPS

    return tuple(
        ActionSpec(
            name=f"launch_{app_name}",
            category=ActionCategory.EXECUTE,
            description=f"Lancer « {app_name} » (modules/automation_manager.py, liste blanche réelle)",
        )
        for app_name in sorted(WHITELISTED_APPS)
    )


# ── RÉEL : core/os_controller.py (Brique 2, 08/08/2026) ─────────────────
#
# get_brightness/set_brightness restent ASPIRATIONNELS : aucun callable
# réel derrière (aucune bibliothèque de luminosité écran retenue cette
# session) — voir ILLUSTRATIVE_ACTIONS ci-dessous, qui ne contient plus
# que ce qui n'existe vraiment pas encore.
def os_controller_actions() -> tuple[ActionSpec, ...]:
    """
    ActionSpec réels pour core/os_controller.py — même patron que
    automation_manager_actions() : générés à chaque appel plutôt que
    recopiés, pour ne jamais dériver d'une méthode ajoutée/retirée là-bas.

    move_file/rename_file/take_screenshot = EXECUTE (écrit un fichier ou
    produit un effet externe, journalisé). set_volume/write_clipboard =
    WRITE (paramètre système réversible, confirmé mais pas journalisé par
    DecisionEngine — OSController journalise lui-même chaque appel dans
    action_log, y compris READ, ce qui est plus large que
    LOGGED_CATEGORIES ici). get_volume/read_clipboard = READ, jamais de
    confirmation.
    """
    return (
        ActionSpec("move_file", ActionCategory.EXECUTE, "Déplacer un fichier entre dossiers autorisés"),
        ActionSpec("rename_file", ActionCategory.EXECUTE, "Renommer un fichier dans un dossier autorisé"),
        ActionSpec("take_screenshot", ActionCategory.EXECUTE, "Capturer l'écran"),
        ActionSpec("set_volume", ActionCategory.WRITE, "Changer le niveau sonore"),
        ActionSpec("write_clipboard", ActionCategory.WRITE, "Écrire dans le presse-papier"),
        ActionSpec("get_volume", ActionCategory.READ, "Lire le niveau sonore actuel"),
        ActionSpec("read_clipboard", ActionCategory.READ, "Lire le contenu du presse-papier"),
    )


# ── ASPIRATIONNEL : aucun callable réel derrière, aucun de ces noms ─────
# n'existe dans le projet aujourd'hui. Sert d'exemple de catégorisation
# pour un futur chantier (luminosité écran) — pas une liste de ce qui est
# construit. Ne pas confondre avec automation_manager_actions() ou
# os_controller_actions() ci-dessus.
ILLUSTRATIVE_ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec("get_brightness", ActionCategory.READ, "Lire la luminosité actuelle de l'écran"),
    ActionSpec("set_brightness", ActionCategory.WRITE, "Changer la luminosité de l'écran"),
)


class DecisionEngine:
    """
    Décide si une action peut s'exécuter directement ou doit être
    confirmée, journalise les exécutions. Ne contient AUCUNE action réelle
    — seulement la structure de décision, appliquée à des callables fournis
    par l'appelant.

    `confirm` : callable (ActionSpec) -> bool, consulté pour WRITE/EXECUTE.
    Sans confirmation injectée : refus systématique. Même principe que
    `is_sensitive()` qui ne consulte jamais un classifieur (CLAUDE.md) —
    un mécanisme de confirmation indisponible ne doit jamais avoir pour
    effet d'AUTORISER une action, seulement de la refuser par défaut.

    `log_event` : injecté comme dans security/ et automation_manager —
    ce module ne connaît pas LucasCore.
    """

    def __init__(
        self,
        confirm: Callable[[ActionSpec], bool] | None = None,
        log_event: Callable[[str, str], None] | None = None,
    ) -> None:
        self._actions: dict[str, ActionSpec] = {}
        self.confirm = confirm
        self.log_event = log_event

    def register(self, spec: ActionSpec) -> None:
        self._actions[spec.name] = spec

    def get(self, name: str) -> ActionSpec | None:
        return self._actions.get(name)

    def requires_confirmation(self, name: str) -> bool:
        return self._require(name).category in CONFIRMATION_REQUIRED

    def request(self, name: str, run: Callable[[], object]) -> object:
        """
        Exécute `run` si l'action est autorisée, lève ActionDenied sinon.

        `run` n'est appelé QUE si l'action est passée — jamais avant, pour
        qu'un WRITE/EXECUTE refusé ne produise strictement aucun effet.
        """
        spec = self._require(name)

        if spec.category in CONFIRMATION_REQUIRED:
            approved = self.confirm is not None and self.confirm(spec)
            if not approved:
                self._log("decision_denied", spec.name)
                raise ActionDenied(
                    f"Action refusée : « {spec.name} » "
                    "(confirmation requise, absente ou refusée)"
                )

        result = run()

        if spec.category in LOGGED_CATEGORIES:
            self._log("decision_executed", spec.name)

        return result

    def _require(self, name: str) -> ActionSpec:
        spec = self._actions.get(name)
        if spec is None:
            raise ActionDenied(f"Action inconnue, hors liste blanche : « {name} »")
        return spec

    def _log(self, event_type: str, details: str) -> None:
        if self.log_event is not None:
            self.log_event(event_type, details[:200])
