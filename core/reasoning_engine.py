# core/reasoning_engine.py — chain-of-thought déterministe pour les
# questions complexes (IDEAS.md #59, v1 minimal)
#
# Pattern explicitement autorisé par CLAUDE.md règle 12 (précision du
# 01/08/2026) : « une classe ReasoningEngine qui enchaîne plusieurs
# prompts (chain-of-thought) » — code Python déterministe qui orchestre
# des appels LLM séquentiels, jamais un agent autonome qui décide
# lui-même d'en enchaîner un autre. Un seul appel LLM à la fois.
#
# v1 volontairement minimal — IDEAS.md #59 catalogue bien plus (débat
# interne 3 personas, analyse multi-critères, arbre de décision 3D),
# explicitement hors périmètre ici. Une seule étape :
#
#   plan() — décompose la question en 2-4 points à couvrir pour bien
#   répondre, SANS répondre. LucasCore (pas ce module) injecte ce plan
#   comme bloc de contexte supplémentaire avant l'appel qui produit la
#   VRAIE réponse — celui qui a déjà accès à la vision, au RAG et à
#   l'historique. Ce module n'a jamais la dernière main sur ce que
#   Cyril lit.
#
# Désactivé par défaut (REASONING_ENGINE_ENABLED, config.py) — voir le
# commentaire de ce flag pour pourquoi.

from dataclasses import dataclass

from core.local_llm import ask_local

PLAN_PROMPT = """Tu prépares un plan de réponse, tu ne réponds pas à la question.

Décompose la question suivante en 2 à 4 points courts : ce qu'il faut
vérifier, comparer ou calculer pour y répondre correctement. Pas de
réponse, pas de blabla — juste les points à couvrir, un par ligne,
commençant par un tiret.

Si la question est simple (salutation, fait ponctuel, calcul trivial,
question qui ne demande qu'un seul fait), réponds uniquement : AUCUN"""

NO_PLAN_NEEDED = "AUCUN"


@dataclass
class ReasoningResult:
    """
    `plan` vide et `used_reasoning` à False dans deux cas distincts :
    la question ne le justifiait pas (AUCUN), ou l'appel a échoué.
    LucasCore n'a pas besoin de les distinguer — dans les deux cas, il
    continue sans bloc de plan supplémentaire plutôt que d'échouer.
    """

    plan: str
    used_reasoning: bool


class ReasoningEngine:
    """
    Décompose une question complexe en points à couvrir, avant que
    LucasCore ne construise sa réponse. Ne répond jamais elle-même —
    voir l'en-tête du module.
    """

    def plan(self, question: str, context: str = "") -> ReasoningResult:
        if not question.strip():
            return ReasoningResult(plan="", used_reasoning=False)

        messages = [{"role": "system", "content": PLAN_PROMPT}]
        if context:
            messages.append({
                "role": "system",
                "content": f"Échange précédent, pour contexte :\n{context}",
            })
        messages.append({"role": "user", "content": question})

        raw = ask_local(messages)

        # ask_local() ne lève jamais — une panne Ollama revient comme une
        # chaîne préfixée "[Erreur]" (voir core/local_llm.py). Un plan
        # indisponible doit dégrader la réponse, jamais l'empêcher.
        if raw.startswith("[Erreur]"):
            return ReasoningResult(plan="", used_reasoning=False)

        cleaned = raw.strip()
        if cleaned.upper().startswith(NO_PLAN_NEEDED):
            return ReasoningResult(plan="", used_reasoning=False)

        return ReasoningResult(plan=cleaned, used_reasoning=True)
