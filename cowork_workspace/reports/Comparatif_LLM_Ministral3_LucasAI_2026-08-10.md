# Comparatif LLM — Ministral 3 8B comme candidat, 10/08/2026

**Demandé par** : Cyril, veille modèles (CLAUDE.md règle 12)
**Objectif initial** : mesurer Mistral 3 8B (VRAM, tokens/s, qualité du
français à l'oral) et comparer au correctif de prompt déjà en place,
pour savoir si un gain viendrait du modèle, du prompt, ou des deux.

**⚠️ Le résultat mesuré change la question posée.** Avant de parler de
qualité orale, un problème plus fondamental et plus grave est apparu :
les deux modèles testés ne répondent pas de façon fiable à la question
posée avec le prompt système actuel de Luca's. Ce rapport documente ce
qui a été mesuré, pas ce qui était espéré.

## 1. Vérification du tag exact (ne pas deviner)

"Mistral 3 8B" ne correspond à aucun tag Ollama sous ce nom. Vérifié via
recherche + `ollama.com/library` : le modèle réel s'appelle **Ministral
3**, tag `ministral-3:8b` (famille `mistral3`, 8,9 B paramètres,
quantification Q4_K_M, 6,0 Go sur disque). Déjà présent sur cette machine
(`ollama list` : pull effectué il y a 2 jours, jamais mesuré ni
documenté avant ce rapport).

## 2. Mesures techniques réelles

VRAM mesurée via `ollama ps` juste après une génération réelle (pas un
modèle à vide) ; tokens/s calculés depuis `eval_count`/`eval_duration`
retournés par Ollama lui-même, pas estimés.

| Modèle | Paramètres | VRAM (chargé) | Tokens/s | Latence typique |
|---|---|---|---|---|
| `ministral-3:8b` | 8,9 B | **5,25-5,38 Go** | **~130-136 tok/s** | 6,9-7,9 s |
| `qwen3:14b` (déjà connu, remesuré aujourd'hui) | 14,8 B | 8,98 Go | ~86 tok/s | 11,3-14,3 s |
| `gpt-oss:20b` (actuel, production) | 20,9 B | 12,5 Go | — (non remesuré ici) | — |

Ministral 3 8B est nettement plus léger et plus rapide que les deux
autres — sur ces deux critères seuls, un excellent candidat.
**⚠️ Ces chiffres ne suffisent pas à trancher — voir §3.**

## 3. 🔴 Problème de fiabilité trouvé en testant — pas une question de style

Trois questions réelles envoyées à `ministral-3:8b` ET `qwen3:14b`, avec
le VRAI prompt que `core/lucas_core.py::_build_messages()` construit
(système + contexte monde + instruction de style oral — voir ROADMAP
§5.86 pour ce dernier bloc, ajouté aujourd'hui) :

- **Aucun des deux modèles n'a répondu à la question posée**, dans
  aucun des trois cas. Les deux ont produit des réponses hallucinées,
  sans rapport avec la question :
  - `ministral-3:8b` invente un fil Reddit sur "l'agent Hermes pour
    Openclaw", prétend voir ce que Cyril fait sur son PC, invente un
    fichier `releves_juillet.csv` et propose de l'ouvrir tout seul.
  - `qwen3:14b` part sur un exposé générique sur "les interfaces IA
    tendances" (Alexa, ChatGPT, MidJourney) sans lien avec la question.

- **Piste explorée et confirmée en partie** : la fenêtre active réelle
  de Cyril au moment du test était une recherche Google sur "les
  interfaces IA les plus tendance... style OpenClaw, Open WebUI" — ce
  texte est légitimement inclus dans le contexte système du prompt
  (`format_for_prompt`, contexte monde). Les deux modèles ont
  manifestement lu ce titre de fenêtre et répondu SUR CE SUJET au lieu
  de répondre à la vraie question — la présence de "OpenClaw" dans la
  réponse de Ministral n'est pas une coïncidence.

- **Mais ce n'est pas l'explication complète.** Un second test, avec le
  contexte "cloud" (qui exclut justement le titre de fenêtre —
  `core/lucas_core.py`, `include_window=not is_cloud`), montre le MÊME
  échec : les deux modèles inventent encore des scénarios sans rapport
  (fichier CSV de relevés bancaires, dossier "Finance") — cette fois en
  confondant la LISTE DES CAPACITÉS du prompt système ("Finance : lire
  et catégoriser des relevés bancaires...") avec une conversation déjà
  en cours sur ce sujet, au lieu de traiter "Résume ce que tu sais
  faire" comme une vraie question à laquelle répondre.

**Conclusion honnête** : le prompt système actuel de Luca's — construit
et validé pour `gpt-oss:20b`, qui le suit de façon fiable depuis des
mois de mesures (ROADMAP.md, toutes les campagnes précédentes) — est
manifestement TROP DENSE ou structuré d'une façon que ces deux modèles
plus petits ne suivent pas correctement. Ce n'est pas une question de
manque de rapidité ou de VRAM (les deux sont plus légers et plus rapides
que `gpt-oss:20b`) : c'est un problème de FIABILITÉ à suivre des
instructions, plus grave qu'une question de style oral.

## 4. Ce qui n'a délibérément PAS été fait

**L'étape d'écoute par Cyril n'a pas été préparée** (pas de synthèse TTS
des réponses) : juger la qualité orale de phrases hallucinées, sans
rapport avec la question posée, n'aurait aucun sens. Cette étape reste à
faire UNE FOIS le problème de fiabilité compris ou contourné — pas avant.

**La comparaison "gain du modèle vs gain du prompt"** demandée à
l'origine n'a pas pu être menée comme prévu : `ORAL_STYLE_INSTRUCTION`
(ajoutée aujourd'hui, ROADMAP §5.86) est bien présente dans TOUS les
prompts testés ici, donc les deux modèles ont eu la même consigne de
style — mais comme aucun des deux n'a répondu à la question elle-même,
il est impossible de juger si le style, lui, était mieux suivi.

## 5. Effet de bord signalé — VRAM de production temporairement libérée

Charger `ministral-3:8b` puis `qwen3:14b` pour ces mesures a évincé
`gpt-oss:20b` de la VRAM (16 Go au total, `gpt-oss:20b` seul en prend déjà
12,5 Go — pas de place pour un second modèle en même temps). `gpt-oss:20b`
a été rechargé et vérifié actif (`ollama ps`) immédiatement après ces
tests. Le téléphone de Cyril était connecté pendant une partie de cette
session (vu dans les logs serveur) — si une question réelle est arrivée
pendant la fenêtre de test, elle aurait attendu le rechargement du modèle
de production plutôt que d'échouer, mais le délai réel n'a pas été
mesuré.

## 6. Recommandation

**Ne pas retenir Ministral 3 8B ni qwen3:14b en l'état** — VRAM et
vitesse excellentes, mais un modèle qui invente des scénarios en confondant
la LISTE DE SES PROPRES CAPACITÉS avec une tâche en cours n'est pas
utilisable, quelle que soit sa qualité de français. Deux pistes pour une
prochaine session, non commencées ici (hors périmètre de cette demande) :

1. Tester ces deux modèles avec une version RACCOURCIE du prompt (retirer
   un bloc à la fois : contexte monde, présence, ré-ancrage) pour isoler
   ce qui, précisément, les fait dérailler — gpt-oss:20b tolère ce prompt
   complet, ces deux-là visiblement pas.
2. Si un modèle plus petit reste souhaité pour sa vitesse/légèreté un
   jour, il faudra soit l'adapter (prompt spécifique, plus court), soit
   accepter que le compromis vitesse/fiabilité ne soit pas encore mûr.

Aucun changement de production. `config.py::MODEL_NAME` reste
`gpt-oss:20b`, inchangé.
