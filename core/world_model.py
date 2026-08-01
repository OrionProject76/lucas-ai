# core/world_model.py — Snapshot de l'état système, en RAM, pas de persistance lourde
#
# Voir VISION_LONG_TERME.md section 2, Pilier 2 : mémoire à 3 niveaux
# (court terme / long terme / procédurale). Ce module fournit le "court
# terme système" — un instantané léger, jamais un historique complet.
#
# Ce code était dupliqué dans api/server.py — centralisé ici pour que
# l'API et OrionCore (donc l'UI PySide6 aussi) utilisent exactement la
# même logique, sans divergence possible entre les deux.

import psutil


def get_snapshot() -> dict:
    """
    Retourne un instantané léger de l'état du système.
    Rafraîchi à la demande, jamais stocké tel quel (pas de table
    "snapshots" — seuls les événements significatifs sont persistés,
    voir memory/memory_manager.py::save_event).
    """
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.3),
        "ram_percent": psutil.virtual_memory().percent,
        "active_window": _get_active_window_title(),
    }


def _get_active_window_title() -> str:
    """
    Titre de la fenêtre active (Windows uniquement).
    Fallback gracieux si pywin32 absent — ne doit jamais faire planter
    l'appelant, juste renvoyer une info moins précise.
    """
    try:
        import win32gui  # pywin32
        hwnd = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(hwnd) or "Inconnu"
    except ImportError:
        return "pywin32 non installé"
    except Exception:  # noqa: BLE001 — le World Model ne doit jamais faire
        # tomber l'appelant : une info moins précise vaut mieux qu'un crash.
        return "Inconnu"


# Événements internes à Orion : ils décrivent sa propre plomberie, pas
# l'environnement de Cyril. Les injecter dans le prompt n'apporte rien au
# LLM et réinjecterait des extraits sensibles (voir voice_manager._log)
# dans des conversations qui n'ont rien à voir.
INTERNAL_EVENT_PREFIXES = ("tts_",)


def format_events_for_prompt(events: list[tuple[str, str, str]]) -> str:
    """
    Formate les événements système récents pour le prompt.

    `events` vient de MemoryManager.load_recent_events() :
    (event_type, details, created_at), du plus récent au plus ancien.

    Retourne une chaîne vide s'il n'y a rien de pertinent à dire — dans ce
    cas l'appelant n'ajoute aucun message système, plutôt qu'un bloc vide
    qui consomme du contexte pour rien.
    """
    relevant = [
        (event_type, details)
        for event_type, details, _created_at in events
        if not event_type.startswith(INTERNAL_EVENT_PREFIXES)
    ]
    if not relevant:
        return ""

    lines = [f"- {event_type}{f' : {details}' if details else ''}" for event_type, details in relevant]
    return "[Événements système récents, du plus récent au plus ancien :\n" + "\n".join(lines) + "]"


def format_for_prompt(snapshot: dict) -> str:
    """
    Formate le snapshot en une courte phrase à injecter dans le prompt
    système du LLM. Reste bref — inutile de noyer le contexte du modèle
    avec des chiffres si ce n'est pas pertinent pour la question posée.
    """
    return (
        f"[Contexte système : CPU {snapshot['cpu_percent']}%, "
        f"RAM {snapshot['ram_percent']}%, "
        f"fenêtre active « {snapshot['active_window']} »]"
    )
