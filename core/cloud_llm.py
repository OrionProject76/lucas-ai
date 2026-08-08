# core/cloud_llm.py — IA cloud (API Anthropic), escalade explicite seulement
#
# Brique 1 du noyau minimal, 08/08/2026 — voir ROADMAP.md. Jamais le chemin
# par défaut : core/router.py décide, ce module exécute. is_sensitive()
# (core/router.py) garde toute donnée sensible strictement locale, en amont
# de tout appel ici — jamais contourné dans ce fichier.

from __future__ import annotations

from config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_EFFORT,
    ANTHROPIC_MAX_TOKENS,
    ANTHROPIC_MODEL,
    ANTHROPIC_PRICE_INPUT_PER_MTOK,
    ANTHROPIC_PRICE_OUTPUT_PER_MTOK,
)


def _to_anthropic_format(messages: list[dict]) -> tuple[str, list[dict]]:
    """
    L'API Anthropic sépare le system prompt du tableau `messages` (jamais un
    rôle "system" dedans) — contrairement au format Ollama utilisé partout
    ailleurs dans ce projet : core/lucas_core.py::_build_messages() injecte
    PLUSIEURS blocs "system" intercalés dans la même liste. Concaténés ici
    dans l'ordre ; user/assistant passent tels quels.
    """
    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    converted = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m.get("role") in ("user", "assistant")
    ]
    return "\n\n".join(system_parts), converted


def _record_usage(input_tokens: int, output_tokens: int) -> None:
    """
    Journalise le coût réel de cet appel dans `cloud_usage`
    (memory/memory_manager.py), pour core/router.py::cloud_budget_available()
    et cloud_budget_warning(). Tarifs USD comparés à un plafond EUR sans
    conversion de change — simplification assumée, voir config.py.
    """
    from memory import memory_manager

    cost_eur = (
        input_tokens / 1_000_000 * ANTHROPIC_PRICE_INPUT_PER_MTOK
        + output_tokens / 1_000_000 * ANTHROPIC_PRICE_OUTPUT_PER_MTOK
    )
    # db_path=memory_manager.DB_PATH explicite, jamais MemoryManager() nu —
    # voir la même précaution dans core/router.py::cloud_budget_available()
    # (ROADMAP.md §5.68, piège du paramètre par défaut figé).
    memory = memory_manager.MemoryManager(db_path=memory_manager.DB_PATH)
    try:
        memory.record_cloud_usage(input_tokens, output_tokens, cost_eur)
    finally:
        memory.close()


def ask_cloud(messages: list[dict]) -> str:
    """
    Envoie la conversation à l'API Anthropic (claude-opus-5 — modèle par
    défaut imposé sauf demande contraire explicite de Cyril, voir la skill
    claude-api). Jamais appelé sur une donnée sensible : core/router.py
    garde is_sensitive() strictement en tête de route(), avant tout test de
    mot-clé cloud — cette fonction ne reçoit donc jamais ce qui ne doit pas
    sortir.

    Toujours un message lisible, jamais d'exception qui remonte — même
    philosophie que modules/automation_manager.py::open_app().
    """
    if not ANTHROPIC_API_KEY:
        return (
            "[Cloud non configuré] Aucune clé Anthropic enregistrée — voir "
            "scripts/set_anthropic_key.py pour l'enregistrer dans le "
            "Gestionnaire d'identification Windows."
        )

    import anthropic

    system, converted = _to_anthropic_format(messages)
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    try:
        # `converted` est un `list[dict]` générique (format Ollama partagé
        # avec local_llm.py), pas le TypedDict `MessageParam` que mypy
        # veut — forme runtime correcte (testée), friction de typage.
        response = client.messages.create(  # type: ignore[call-overload]
            model=ANTHROPIC_MODEL,
            max_tokens=ANTHROPIC_MAX_TOKENS,
            system=system,
            messages=converted,
            output_config={"effort": ANTHROPIC_EFFORT},
        )
    except anthropic.AuthenticationError:
        return "[Cloud] Clé Anthropic invalide ou révoquée."
    except anthropic.RateLimitError:
        return "[Cloud] Limite de requêtes Anthropic atteinte — réessaie dans un instant."
    except anthropic.APIConnectionError:
        return "[Cloud] Impossible de joindre l'API Anthropic (réseau)."
    except anthropic.APIStatusError as exc:
        return f"[Cloud] Erreur Anthropic ({exc.status_code})."

    _record_usage(response.usage.input_tokens, response.usage.output_tokens)

    # ⚠️ Vérifié AVANT de lire response.content : les garde-fous de sécurité
    # d'Anthropic peuvent refuser une requête légitime (faux positif sur un
    # sujet cybersécurité/bio adjacent) — réponse HTTP 200 normale, contenu
    # vide ou partiel. Un code qui lit content[0] sans ce test plante sur
    # un refus. Voir la skill claude-api, Claude Opus 5.
    if response.stop_reason == "refusal":
        return (
            "[Cloud] La question a été refusée par les garde-fous "
            "d'Anthropic — reformule ou reste en local."
        )

    text = next((block.text for block in response.content if block.type == "text"), "")
    return text or "[Cloud] Réponse vide."
