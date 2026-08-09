# modules/capability_registry.py — registre en lecture des capacités de
# Luca's (Bureau de l'IA, E-5, IDEAS.md #102 groupe E — brief nommé
# "Poste de Commandement IA", renommé par Cyril après coup)
#
# Brief : cowork_workspace/BRIEF_POSTE_COMMANDEMENT_IA_E5.md. Étape
# préalable (§3) : exploré modules/, core/, croisé avec l'audit de
# nettoyage du 09/08/2026
# (cowork_workspace/reports/Audit_Nettoyage_LucasAI_2026-08-09.md) — la
# liste ci-dessous EXCLUT délibérément modules/stt_manager.py, identifié
# comme orphelin par cet audit (plus aucune référence dans le code réel
# hors son propre test).
#
# Lecture seule stricte (brief §4) : ce module ne modifie rien, n'installe
# rien, ne configure rien — il décrit ce qui existe déjà.
#
# Deux natures de statut, jamais mélangées :
# - Un vrai drapeau dans config.py (VLM_ENABLED, REASONING_ENGINE_ENABLED,
#   OCR_ENABLED, VISION_ENABLED) → le statut est CALCULÉ à l'appel, jamais
#   figé en texte : si Cyril change le drapeau, ce registre le reflète
#   sans mise à jour manuelle de ce fichier.
# - Pas de drapeau (le reste, câblé ou non de façon structurelle) →
#   statut figé, reflétant une exploration réelle du code à VERIFIED_AT.
#   Une fausse promesse de "toujours à jour" serait pire qu'une date
#   explicite — même principe que le tableau de modèles de CLAUDE.md, qui
#   porte la même limite et la même honnêteté à ce sujet.

from __future__ import annotations

from dataclasses import dataclass

import config

# Date de la dernière vérification par exploration réelle du code (pas
# supposée) des entrées SANS drapeau config.py — à refaire si le code
# change significativement, pas un instantané garanti éternellement exact.
VERIFIED_AT = "2026-08-09"

STATUS_ACTIVE = "actif"
STATUS_DISABLED = "inactif"
STATUS_BUILT_NOT_WIRED = "construit, non branché"
STATUS_MANUAL = "manuel"


@dataclass(frozen=True)
class Capability:
    name: str
    category: str
    description: str
    status: str
    detail: str


def list_capabilities() -> list[Capability]:
    """Instantané complet, recalculé à chaque appel — jamais mis en cache."""
    return [
        # ── Cœur ─────────────────────────────────────────────────────────
        Capability(
            name="Routeur hybride local/cloud",
            category="Cœur",
            description="Décide, question par question, si Ollama (local) ou le cloud répond — jamais une donnée sensible vers le cloud.",
            status=STATUS_ACTIVE,
            detail="core/router.py, core/local_llm.py, core/cloud_llm.py.",
        ),
        # ── Perception ───────────────────────────────────────────────────
        Capability(
            name="Lecture d'écran (OCR)",
            category="Perception",
            description="Extrait le texte affiché à l'écran pour répondre aux questions qui le concernent.",
            status=STATUS_ACTIVE if config.OCR_ENABLED else STATUS_DISABLED,
            detail="modules/ocr_engine.py, modules/vision_manager.py — déclenché via core/intent.py.",
        ),
        Capability(
            name="Description visuelle de la scène (VLM)",
            category="Perception",
            description="Décrirait la mise en page/le contenu visuel de l'écran au-delà du texte brut.",
            status=STATUS_ACTIVE if config.VLM_ENABLED else STATUS_DISABLED,
            detail="Désactivé (config.py::VLM_ENABLED) — llava mesuré 0/4 en lecture d'écran réelle.",
        ),
        Capability(
            name="Classifieur d'intention (écran / documents / aucun)",
            category="Perception",
            description="Décide quelle capacité consulter pour une question donnée — jamais une décision de sécurité.",
            status=STATUS_ACTIVE if config.INTENT_CLASSIFIER_ENABLED else STATUS_DISABLED,
            detail="core/intent.py, appelé par core/router.py.",
        ),
        # ── Mémoire & World Model ────────────────────────────────────────
        Capability(
            name="Mémoire à 5 types",
            category="Mémoire & World Model",
            description="Souvenirs typés (épisodique/sémantique/procédural/émotionnel/prospectif), distincts du transcript de chat.",
            status=STATUS_ACTIVE,
            detail="memory/memory_manager.py (remember/recall/forget).",
        ),
        Capability(
            name="Recherche documentaire (RAG)",
            category="Mémoire & World Model",
            description="Cherche dans les documents personnels indexés pour répondre avec leur contenu réel.",
            status=STATUS_ACTIVE,
            detail="modules/rag_manager.py (ChromaDB), déclenché via core/intent.py.",
        ),
        Capability(
            name="World Model",
            category="Mémoire & World Model",
            description="Instantané système (CPU/RAM/fenêtre active/heure) joint au contexte de chaque réponse.",
            status=STATUS_ACTIVE,
            detail="core/world_model.py.",
        ),
        Capability(
            name="Repondération mémoire (confiance/provenance)",
            category="Mémoire & World Model",
            description="Annote chaque souvenir de sa fiabilité — l'exploitation en aval (repondérer une réponse) n'est pas encore câblée.",
            status=STATUS_ACTIVE,
            detail="core/memory_weighting.py — annote déjà, ne repondère pas encore une réponse finale.",
        ),
        # ── Cognition & Raisonnement ─────────────────────────────────────
        Capability(
            name="Raisonnement en chaîne (chain-of-thought)",
            category="Cognition & Raisonnement",
            description="Décomposerait une question complexe en points à couvrir avant de répondre.",
            status=STATUS_ACTIVE if config.REASONING_ENGINE_ENABLED else STATUS_DISABLED,
            detail="Désactivé (config.py::REASONING_ENGINE_ENABLED) — changerait la réponse à toute question complexe, pas activé sans validation de Cyril sur de vraies questions.",
        ),
        Capability(
            name="Modes AURA (ton)",
            category="Cognition & Raisonnement",
            description="Détecte 8 modes de ton (ex. concentration, fatigue) — ajuste le TON de la réponse, jamais une action système.",
            status=STATUS_ACTIVE,
            detail="core/aura_modes.py.",
        ),
        Capability(
            name="Moteur de décision (lecture auto, écriture/exécution confirmées)",
            category="Cognition & Raisonnement",
            description="Structure qui déciderait quelles actions demandent confirmation — aujourd'hui câblé uniquement pour le lancement d'applications.",
            status=STATUS_ACTIVE,
            detail="core/decision_engine.py — seule modules/automation_manager.py y est réellement enregistré ; core/os_controller.py ne l'est pas (voir plus bas).",
        ),
        # ── Action & Expression ──────────────────────────────────────────
        Capability(
            name="Finance CSV",
            category="Action & Expression",
            description="Importe et catégorise des relevés bancaires CSV, jamais de connexion bancaire directe.",
            status=STATUS_ACTIVE,
            detail="modules/finance_manager.py, modules/finance_categorizer.py.",
        ),
        Capability(
            name="Calculatrice",
            category="Action & Expression",
            description="Évalue une expression arithmétique mentionnée dans la question.",
            status=STATUS_ACTIVE,
            detail="modules/calculator.py.",
        ),
        Capability(
            name="Recherche web",
            category="Action & Expression",
            description="Recherche sur le web pour une question qui le demande explicitement, filtrée contre la fuite de données locales.",
            status=STATUS_ACTIVE,
            detail="modules/web_search.py.",
        ),
        Capability(
            name="Météo",
            category="Action & Expression",
            description="Répond aux questions météo pour une ville extraite de la question.",
            status=STATUS_ACTIVE,
            detail="modules/weather_manager.py.",
        ),
        Capability(
            name="Automatisation (liste blanche d'applications)",
            category="Action & Expression",
            description="Lance une application de la liste blanche depuis le chat, sans confirmation à ce jour.",
            status=STATUS_ACTIVE,
            detail="modules/automation_manager.py.",
        ),
        Capability(
            name="OS Controller (fichiers, volume, presse-papier)",
            category="Action & Expression",
            description="Déplacer/renommer un fichier, régler le volume, lire/écrire le presse-papier.",
            status=STATUS_BUILT_NOT_WIRED,
            detail=f"core/os_controller.py — construit et testé, mais importé nulle part hors de son propre test (vérifié {VERIFIED_AT}) : aucune route ni déclenchement chat ne l'appelle aujourd'hui.",
        ),
        Capability(
            name="Synthèse vocale (TTS)",
            category="Action & Expression",
            description="Lit la réponse à voix haute — routée entre edge_tts (cloud) et Piper (local) selon la sensibilité.",
            status=STATUS_ACTIVE,
            detail="modules/voice_manager.py, modules/piper_engine.py.",
        ),
        Capability(
            name="Reconnaissance vocale (STT)",
            category="Action & Expression",
            description="Transcrit un message vocal envoyé depuis le pont mobile.",
            status=STATUS_ACTIVE,
            detail="modules/stt_engine.py, appelé par api/server.py (WebSocket, message \"audio\").",
        ),
        Capability(
            name="Bureau sémantique",
            category="Action & Expression",
            description="Organise/retrouve les documents personnels par sens plutôt que par dossier — lecture seule.",
            status=STATUS_ACTIVE,
            detail="modules/semantic_desktop.py.",
        ),
        # ── Interface & Workspace ────────────────────────────────────────
        Capability(
            name="Avatar",
            category="Interface",
            description="Affiche l'état de Luca's (écoute, parle, réfléchit...) sur PC, mobile et Godot.",
            status=STATUS_ACTIVE,
            detail="ui/avatar_widget.py, static/js/avatar.js, Lucas3D/.",
        ),
        Capability(
            name="Zone Sandbox",
            category="Interface",
            description="Exécute du code proposé dans un environnement isolé (réseau bloqué, fichiers limités) — jamais auto-exécuté.",
            status=STATUS_ACTIVE,
            detail="modules/sandbox_manager.py, modules/sandbox_runner.py.",
        ),
        Capability(
            name="Détecteur d'économies",
            category="Interface",
            description="Repère charges récurrentes, hausses de tarif et doublons probables dans les relevés déjà importés.",
            status=STATUS_ACTIVE,
            detail="modules/savings_detector.py.",
        ),
        Capability(
            name="Workspace",
            category="Interface",
            description="Tableau de bord PC — agrège rapports, demandes, actions, objectifs, sandbox et détecteur d'économies.",
            status=STATUS_ACTIVE,
            detail="modules/workspace_manager.py.",
        ),
        # ── Sécurité ─────────────────────────────────────────────────────
        Capability(
            name="Surveillance sécurité niveau 1",
            category="Sécurité",
            description="Observe (jamais n'agit) : intégrité système, ransomware, persistance suspecte.",
            status=STATUS_ACTIVE,
            detail="security/ (guardian, privacy_shield, ransomware_watch, persistence_watch, monitor) — planifié par lucas_daemon.py (5 min / 15 min).",
        ),
        Capability(
            name="Surveillance VRAM (watchdog)",
            category="Sécurité",
            description="Alerterait avant qu'un dépassement de VRAM ne fasse échouer un chargement de modèle.",
            status=STATUS_MANUAL,
            detail=f"modules/vram_watchdog.py — code réel et testé, mais aucune tâche planifiée ne le démarre automatiquement (vérifié {VERIFIED_AT}, voir l'audit de nettoyage du 09/08/2026) : à lancer à la main.",
        ),
    ]
