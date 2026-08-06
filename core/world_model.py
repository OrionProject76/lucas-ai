# core/world_model.py — Snapshot de l'état système, en RAM, pas de persistance lourde
#
# Voir VISION_LONG_TERME.md section 2, Pilier 2 : mémoire à 3 niveaux
# (court terme / long terme / procédurale). Ce module fournit le "court
# terme système" — un instantané léger, jamais un historique complet.
#
# Ce code était dupliqué dans api/server.py — centralisé ici pour que
# l'API et LucasCore (donc l'UI PySide6 aussi) utilisent exactement la
# même logique, sans divergence possible entre les deux.

from datetime import datetime

import psutil

# Jour de semaine construit à la main, pas via strftime("%A") : ce dernier
# dépend de la locale du système, qui peut rendre "Saturday" au lieu de
# "samedi" selon la machine — un détail invisible en dev, qui aurait fait
# halluciner le jour en plus de l'heure sur une machine mal localisée.
_WEEKDAYS_FR = (
    "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
)


def get_snapshot() -> dict:
    """
    Retourne un instantané léger de l'état du système.
    Rafraîchi à la demande, jamais stocké tel quel (pas de table
    "snapshots" — seuls les événements significatifs sont persistés,
    voir memory/memory_manager.py::save_event).
    """
    # Heure LOCALE délibérée : ce snapshot alimente le prompt (« il est
    # 22h14, mercredi »). En UTC, Luca's annoncerait à Cyril une heure
    # qui n'est pas celle de sa pendule.
    now = datetime.now()  # noqa: DTZ005
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.3),
        "ram_percent": psutil.virtual_memory().percent,
        "gpu_percent": _get_gpu_load(),
        "active_window": _get_active_window_title(),
        # ⚠️ Ajouté le 05/08/2026 en construisant les modes AURA. Le titre
        # SEUL ne suffit pas : sur cette machine, le terminal actif
        # s'intitulait « ⠐ Valider avatar Godot et relancer serveur API » —
        # aucune trace de « terminal », donc invisible pour une détection
        # par titre. Le nom du process, lui, est stable quoi que
        # l'utilisateur écrive dans sa fenêtre. Les deux sont conservés :
        # le titre reste indispensable pour tout ce qui vit dans un
        # navigateur (YouTube, Netflix, une doc), où le process vaut
        # toujours « chrome ».
        "active_process": _get_active_process_name(),
        # ⚠️ Trouvé en usage réel (Cyril, 02/08/2026) : Luca's n'avait
        # accès à l'heure réelle NULLE PART dans son contexte. Face à une
        # question sur l'heure, elle inventait une valeur plausible ("il
        # est environ 14h30") ou, une fois, recopiait un gabarit de
        # placeholder issu de son propre entraînement au lieu d'un vrai
        # chiffre ("il est [heure actuelle]"). Les deux sont le même
        # symptôme que le RAG ou la vision sans résultat : rien ne
        # l'empêchait de deviner. L'horloge réelle règle la question à la
        # racine — plus besoin de deviner ce qu'on peut lire.
        "local_time": f"{_WEEKDAYS_FR[now.weekday()]} {now.strftime('%d/%m/%Y %H:%M')}",
    }


def _get_gpu_load() -> float:
    """
    Charge GPU en pourcentage, 0.0 si illisible.

    Vaut la peine d'être suivie ici précisément parce que la RTX 5080 est
    partagée entre Ollama et le rendu Godot (VISION_LONG_TERME.md §3) :
    voir la carte grimper explique une réponse lente ou un chargement de
    modèle, là où CPU et RAM ne diraient rien.

    Reprise du service Lucas3D supprimé, qui alimentait la jauge GPU du
    HUD — sans elle, ce cadran serait resté à zéro pour toujours.
    """
    try:
        import GPUtil

        gpus = GPUtil.getGPUs()
        return round(gpus[0].load * 100, 1) if gpus else 0.0
    except Exception:  # noqa: BLE001 — pilote absent, machine sans GPU
        # dédié : une jauge vide vaut mieux qu'un World Model en panne.
        return 0.0


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


def _get_active_process_name() -> str:
    """
    Nom du process propriétaire de la fenêtre active, sans extension
    (« chrome », « notepad »), chaîne vide si illisible.

    LECTURE SEULE. `GetWindowThreadProcessId` interroge une fenêtre, il
    n'en manipule aucune : rien à voir avec le registre d'API interdit par
    CLAUDE.md (`SetForegroundWindow`, `ShowWindow`, hooks). Le module
    utilise déjà `win32gui.GetForegroundWindow()` juste au-dessus, dans le
    même esprit.

    Toute panne rend "" : le World Model ne doit jamais faire tomber son
    appelant, une info manquante vaut mieux qu'une exception.
    """
    try:
        import psutil
        import win32gui
        import win32process

        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if not pid:
            return ""
        nom = psutil.Process(pid).name()
        return nom[:-4].lower() if nom.lower().endswith(".exe") else nom.lower()
    except Exception:  # noqa: BLE001 — voir docstring
        return ""


# Événements internes à Lucas : ils décrivent sa propre plomberie, pas
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


def format_for_prompt(snapshot: dict, include_window: bool = True) -> str:
    """
    Formate le snapshot en une courte phrase à injecter dans le prompt
    système du LLM. Reste bref — inutile de noyer le contexte du modèle
    avec des chiffres si ce n'est pas pertinent pour la question posée.

    `include_window=False` retire le titre de la fenêtre active. À utiliser
    pour toute requête cloud : un titre comme « budget_2026.xlsx - Excel »
    ou « releve_bancaire.pdf » est une donnée personnelle en soi, même
    quand la question posée est anodine. CPU, RAM et l'heure ne disent
    rien de Cyril et restent joints, cloud compris. Voir CLAUDE.md règle 3.
    """
    parts = [
        f"CPU {snapshot['cpu_percent']}%",
        f"RAM {snapshot['ram_percent']}%",
        f"date et heure actuelles : {snapshot['local_time']}",
    ]
    if include_window:
        parts.append(f"fenêtre active « {snapshot['active_window']} »")

    return "[Contexte système : " + ", ".join(parts) + "]"
