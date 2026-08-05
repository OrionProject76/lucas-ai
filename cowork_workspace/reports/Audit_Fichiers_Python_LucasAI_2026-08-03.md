# Audit des fichiers Python — Luca's AI (ex-OrionAI)

**Date** : 03/08/2026
**Périmètre** : `C:\OrionAI\` parcouru en lecture seule (aucun fichier modifié, déplacé ou supprimé).
**Source de la classification** : lecture intégrale de `ROADMAP.md`, `CLAUDE.md` et `IDEAS.md` (les trois fichiers de référence du projet), croisée avec l'arborescence réelle du disque.

---

## ⚠️ Mise à jour du 04/08/2026 (nuit) — les 2 orphelins de ce rapport ont été câblés

Ce rapport reste un instantané au 03/08/2026 — rien n'a été réécrit ci-dessous, cette
section documente seulement ce qui a changé depuis. Sur décision explicite de Cyril
("Traite les 3 modules orphelins et chat_widget.py"), Claude Code a câblé les deux
fichiers classés ❌ ci-dessous dans le chat réel plutôt que de les supprimer :

- **`modules/calculator.py`** → câblé (`should_use_calculator()`/`extract_calculation()`,
  `core/router.py`) — le calcul est fait en Python, jamais deviné par le LLM.
- **`modules/weather_manager.py`** → câblé (`should_use_weather()`/`extract_city()`,
  `core/router.py`). **Un bug réel a été trouvé au passage** : `?format=3` (wttr.in)
  rend en réalité UNE SEULE ligne, pas quatre comme le supposait le parsing existant —
  ce module n'avait donc JAMAIS renvoyé de météo réelle, malgré des tests unitaires
  tous verts (ils ne mockaient que la forme supposée). Corrigé avec un format
  personnalisé (`%l|%C|%t|%w|%h`) et une détection d'erreur par code HTTP.

Un troisième module dans la même situation, découvert seulement le 04/08 (après ce
rapport, donc absent de la table ❌ ci-dessous) : **`modules/web_search.py`** — câblé
aussi, avec une dépendance cassée (`duckduckgo_search`→`ddgs`, le paquet ne renvoyait
plus aucun résultat) trouvée et corrigée en même temps.

Détail complet (design, tests, validation en conditions réelles) : `ROADMAP.md` §5.19
"Traitement des modules orphelins".

---

## Méthodologie

Pour chaque fichier `.py`, le nom exact du fichier a été recherché dans `ROADMAP.md` (et en appui `CLAUDE.md`/`IDEAS.md`) pour vérifier si son statut de test/validation y est explicitement confirmé.

- **✅ Mentionné comme testé** : le nom du fichier apparaît dans `ROADMAP.md` accompagné d'une confirmation explicite de test ou de validation (fichier `test_*.py` cité nommément, décompte de tests, validation en conditions réelles décrite en détail).
- **⚠️ Existe mais statut incertain** : le fichier existe et est utilisé (parfois cité dans l'arborescence de `CLAUDE.md`), mais `ROADMAP.md` ne confirme explicitement ni son statut de test, ni sa couverture — sans pour autant indiquer qu'il serait inutilisé.
- **❌ Semble orphelin** : `ROADMAP.md` **déclare lui-même** que le fichier n'est "branché" nulle part ailleurs dans le code (aucun appelant identifié), même s'il possède parfois un test unitaire propre.

**Limite importante, à lire avant toute action** : cette classification s'appuie sur ce que les trois fichiers de documentation déclarent — je n'ai pas ouvert et analysé chaque fichier `.py` un par un pour retracer moi-même tous les imports du dépôt (accès lecture seule, mission de synthèse uniquement). Les deux cas classés ❌ ci-dessous reprennent un constat déjà posé par `ROADMAP.md` lui-même (audit de fiabilité du 02/08/2026, §5.2) — **à revérifier avec Claude Code (grep des imports réels) avant toute suppression**, conformément à la demande.

## Résumé

| Statut | Nombre de fichiers |
|---|---|
| ✅ Mentionné comme testé | 59 |
| ⚠️ Existe, statut incertain | 21 |
| ❌ Semble orphelin | 2 |
| **Total fichiers `.py` recensés** | **82** |

Dossiers explorés : racine, `core/`, `modules/`, `memory/`, `ui/`, `api/`, `security/`, `demos/`. Les dossiers `tools/`, `training/`, `models/`, `missions/` ne contiennent aucun fichier `.py` (respectivement : un exécutable, vide, vide, des fichiers `.md`). Le dossier `Lucas3D/` (Godot) ne contient que du GDScript (`.gd`), pas de Python. `venv/`, `__pycache__/`, `.git/` et les caches d'outils (`.mypy_cache`, `.ruff_cache`, `.pytest_cache`, `.aider.tags.cache.v4`) ont été exclus de l'analyse (dépendances/artefacts, pas du code du projet).

## ❌ Les 2 fichiers orphelins identifiés

| Fichier | Constat dans ROADMAP.md |
|---|---|
| `modules/calculator.py` | §5.2 (audit de fiabilité 02/08/2026) : correction d'une faille `eval()` critique, testée (`test_calculator.py`), mais **"non branché ailleurs dans le code au moment de la correction"** — aucune trace ultérieure d'un branchement. ⚠️ **Câblé depuis, voir la mise à jour du 04/08/2026 ci-dessus.** |
| `modules/weather_manager.py` | §1 et §5.2 : bug d'import corrigé (plantage à l'import), testé (`test_weather_manager.py`), mais **"Module toujours non branché ailleurs dans le code"** — confirmé encore non câblé au 03/08/2026. ⚠️ **Câblé depuis (04/08/2026) — un second bug réel (parsing wttr.in) trouvé et corrigé au passage, voir la mise à jour ci-dessus.** |

Les deux passent leurs tests unitaires (le code lui-même n'est pas cassé) — le problème est qu'**aucun autre module ne les appelle** d'après ce que `ROADMAP.md` documente. À confirmer avec Claude Code par une recherche d'imports réelle (`from modules.calculator import`, `from modules.weather_manager import`, etc.) avant d'envisager quoi que ce soit.

---

## Détail par dossier

### Racine `C:\OrionAI\`

| Fichier | Statut | Détail |
|---|---|---|
| `main.py` | ✅ | Point d'entrée cité à plusieurs reprises comme support de validation réelle ("Validé via `main.py`, pas seulement par des tests" — RAG, OCR). |
| `config.py` | ✅ | Ses constantes (`HISTORY_BUDGET_CHARS`, `VLM_ENABLED`, `REASONING_ENGINE_ENABLED`, `API_TOKEN`, `RAG_MAX_DISTANCE`...) sont chacune décrites comme mesurées/validées en conditions réelles à travers `ROADMAP.md`. |
| `lucas_daemon.py` | ⚠️ | Orchestrateur confirmé du monitoring sécurité continu (`SecurityMonitor` orchestre les capteurs depuis ce fichier), mais aucun test dédié nommé explicitement pour ce fichier lui-même. |
| `test_automation.py` … `test_world_model.py` (28 fichiers) | ✅ | Font partie de la suite pytest globale, confirmée verte à plusieurs reprises au fil du projet (554 → 575 → 605 → 627 → 686 tests, toujours "tous verts"). Certains sont cités nommément (`test_protocol.py`, `test_router.py`, `test_server.py`, `test_reasoning_engine.py`, `test_semantic_desktop.py`, `test_intent.py`, `test_world_model.py`, `test_avatar.py`, `test_finance.py`, `test_history_budget.py`, `test_index_documents.py`, `test_memory_context.py`, `test_security_status.py`, `test_vision_routing.py`, `test_voice_router.py`, `test_calculator.py`), d'autres non individuellement (`test_dates.py`, `test_integration.py`, `test_modules.py`, `test_ocr.py`, `test_ollama_client.py`, `test_security.py`, `test_stt.py`, `test_text_utils.py`, `test_ui_workers.py`, `test_voice.py`, `test_weather_manager.py`) mais font partie du même décompte global. |

### `core/` — chef d'orchestre, décisions déterministes

| Fichier | Statut | Détail |
|---|---|---|
| `__init__.py` | ⚠️ | Fichier d'initialisation de package, jamais discuté individuellement — exercé indirectement à chaque import de `core.*`. |
| `cloud_llm.py` | ⚠️ | Confirmé utilisé par `core/router.py` (CLAUDE.md : "le code... route déjà vers le cloud (`core/router.py`, `core/cloud_llm.py`)"), mais aucune confirmation explicite de test pour ce fichier précis. |
| `dates.py` | ✅ | Comportement mesuré et corrigé en conditions réelles (leçons RAG : filtrage de dates sur bulletins de salaire réels), implémentation citée nommément dans plusieurs correctifs. |
| `intent.py` | ✅ | "Le corpus de formulations vit dans `test_intent.py`" — classifieur ÉCRAN/DOCUMENTS/AUCUN, tests explicitement cités et enrichis en continu. |
| `llm_worker.py` | ⚠️ | Cité uniquement dans l'arborescence de `CLAUDE.md` (worker `QThread` pour l'UI), aucune confirmation de test individuelle. |
| `local_llm.py` | ⚠️ | Idem — cité seulement dans l'arborescence des fichiers, pas de statut de test explicite. |
| `lucas_core.py` | ✅ | Cœur du système, largement testé (`test_memory_context.py`, `test_world_model.py`, `test_history_budget.py`, `test_vision_routing.py`) et validé en conditions réelles à de multiples reprises. |
| `ollama_client.py` | ⚠️ | Cité seulement dans l'arborescence de `CLAUDE.md`, malgré l'existence d'un `test_ollama_client.py` — `ROADMAP.md` ne le discute pas nommément. |
| `reasoning_engine.py` | ✅ | "8 tests unitaires (`test_reasoning_engine.py`, LLM mocké) + 3 tests d'intégration" — v1 construit et testé le 03/08/2026, désactivé par défaut. |
| `router.py` | ✅ | Très largement testé (`test_router.py`), pièce centrale du routage local/cloud et RAG oui/non. |
| `text_utils.py` | ⚠️ | Cité seulement dans l'arborescence de `CLAUDE.md`, malgré l'existence d'un `test_text_utils.py` — pas de discussion nommée dans `ROADMAP.md`. |
| `world_model.py` | ✅ | "Testé (`test_memory_context.py`, `test_world_model.py`, `test_history_budget.py`)" — explicitement cité. |

### `modules/` — un fichier par domaine

| Fichier | Statut | Détail |
|---|---|---|
| `__init__.py` | ⚠️ | Fichier d'initialisation, non discuté individuellement. |
| `automation_manager.py` | ✅ | Cité explicitement dans l'audit de fiabilité (§5.2) comme ayant des tests réels. |
| `calculator.py` | ❌ | Voir tableau des orphelins ci-dessus — testé mais non branché ailleurs dans le code. ⚠️ Câblé depuis (04/08/2026). |
| `finance_categorizer.py` | ✅ | Confirmé importé et utilisé (§5.2 : "sont bien tous les deux utilisés (imports confirmés)... pas des doublons", en paire avec `finance_manager.py`), intégré au chantier Finance CSV testé. |
| `finance_manager.py` | ✅ | Finance CSV "fermé le 03/08/2026" — 24 tests ajoutés au total, validé en conditions réelles sur données fictives. |
| `ocr_engine.py` | ✅ | Vision écran OCR "fait et validé en conditions réelles (01/08/2026)", couvert par `test_index_documents.py` pour le chemin PDF scanné. |
| `piper_engine.py` | ⚠️ | Cité seulement dans l'arborescence de `CLAUDE.md` (paire avec `voice_manager.py`) ; le moteur Piper est validé en conditions réelles (sortie WAV confirmée) mais ce fichier précis n'est jamais cité nommément dans une confirmation de test. |
| `rag_manager.py` | ✅ | RAG documents personnels "terminé et validé en conditions réelles (01/08/2026)", 39 documents / 229 morceaux. |
| `semantic_desktop.py` | ✅ | "9 tests (`test_semantic_desktop.py`...)" — v1 construit et testé le 03/08/2026. |
| `stt_engine.py` | ✅ | "Déjà écrit et testé, commité le 01/08" — vérifié avec un vrai fichier WAV. |
| `stt_manager.py` | ✅ | Confirmé utilisé et testé (§5.2 : paire avec `stt_engine.py`, "imports confirmés... et leurs tests respectifs"). |
| `vision_manager.py` | ✅ | Cité explicitement dans l'audit de fiabilité (§5.2) comme ayant des tests réels, couvert par `test_vision_routing.py`. |
| `voice_manager.py` | ✅ | TTS (`synthesize_routed()`, `speak()`) validé en conditions réelles (sorties `edge_tts`/Piper vérifiées, mime mp3/wav). |
| `weather_manager.py` | ❌ | Voir tableau des orphelins ci-dessus — bug d'import corrigé et testé, mais jamais branché ailleurs. ⚠️ Câblé depuis (04/08/2026), second bug réel (parsing wttr.in) trouvé et corrigé au passage. |
| `web_search.py` | ✅ | Cité explicitement dans l'audit de fiabilité (§5.2) comme ayant des tests réels ; filtre anti-fuite décrit en détail (§5.1). |

### `memory/` — mémoire de conversation + indexation RAG

| Fichier | Statut | Détail |
|---|---|---|
| `__init__.py` | ⚠️ | Fichier d'initialisation, non discuté individuellement. |
| `index_documents.py` | ✅ | Très largement testé et validé (`test_index_documents.py`), chaîne complète déposer→indexer→calibrer→interroger vérifiée sur le corpus réel de Cyril. |
| `memory_manager.py` | ⚠️ | Central au projet (historique SQLite, table `conversations`), largement utilisé, mais aucun fichier de test dédié n'est cité nommément dans `ROADMAP.md`. |

### `ui/` — interface PySide6

| Fichier | Statut | Détail |
|---|---|---|
| `__init__.py` | ⚠️ | Fichier d'initialisation, non discuté individuellement. |
| `avatar_widget.py` | ✅ | "`test_avatar.py` intermittent mais confirmé sans lien avec le renommage, passe de façon fiable isolément." |
| `chat_widget.py` | ⚠️ | Cité seulement dans le contexte du renommage technique et dans l'arborescence — pas de confirmation de test dédiée. |
| `main_window.py` | ⚠️ | Idem — cité pour le renommage (`last_orion_response`) mais pas de statut de test explicite. |

### `api/` — API FastAPI unique

| Fichier | Statut | Détail |
|---|---|---|
| `__init__.py` | ⚠️ | Fichier d'initialisation, non discuté individuellement. |
| `protocol.py` | ✅ | "Tests : `test_protocol.py`" cité à de nombreuses reprises (nouveaux types de messages `activity`, `speech`, `security_status`...). |
| `server.py` | ✅ | Le fichier le plus testé du projet — `test_server.py` cité massivement (605, 627, 686 tests), validations en conditions réelles répétées. |

### `security/` — niveau 1, observation seule

| Fichier | Statut | Détail |
|---|---|---|
| `__init__.py` | ⚠️ | Fichier d'initialisation, non discuté individuellement. |
| `guardian.py` | ✅ | "Existent en ébauche testée (62 tests)" puis niveau 1 (94 tests). |
| `history.py` | ✅ | Cité explicitement dans le décompte "Niveau 1 clos... une mémoire partagée (`history`), 94 tests". |
| `monitor.py` | ✅ | Cité explicitement comme l'un des cinq capteurs couverts par les 94 tests du Niveau 1. |
| `persistence_watch.py` | ✅ | Cité explicitement, comportement CRITIQUE/WARNING décrit et couvert par les 94 tests du Niveau 1. |
| `privacy_shield.py` | ✅ | "Existent en ébauche testée (62 tests)" puis niveau 1 (94 tests). |
| `ransomware_watch.py` | ✅ | "Existent en ébauche testée (62 tests)" puis niveau 1 ; extension "analyse d'entropie" scopée le 03/08/2026. |
| `status.py` | ✅ | "Tests : `test_security_status.py` (deux vraies bases SQLite temporaires par test...)". |
| `types.py` | ⚠️ | Utilisé par les capteurs testés (classe `Finding`), mais jamais cité avec une confirmation de test qui lui soit propre. |

### `demos/` — scripts de démonstration/calibrage manuels

| Fichier | Statut | Détail |
|---|---|---|
| `calibrate_rag.py` | ✅ | "`demos/calibrate_rag.py` relancé en conditions réelles" (§5.3) — validation manuelle explicitement décrite (au sens "run vérifié", pas suite pytest). |
| `demo_automation.py` | ⚠️ | Jamais mentionné dans `ROADMAP.md`/`CLAUDE.md`. Script de démonstration manuel par nature (pas censé être importé par le reste du code) — l'absence de mention ne signale pas la même anomalie que pour `calculator.py`/`weather_manager.py`, simplement une utilisation réelle non confirmée par la documentation. |
| `demo_avatar.py` | ⚠️ | Idem. |
| `demo_vision.py` | ⚠️ | Idem. |
| `demo_voices.py` | ⚠️ | Idem. |

---

## Recommandation

Avant toute suppression, faire confirmer par Claude Code (accès en écriture au dépôt) un grep direct des imports réels de `modules/calculator.py` et `modules/weather_manager.py` dans l'ensemble du code (`core/`, `api/`, `ui/`, tests inclus) — cette synthèse s'appuie sur le constat déjà documenté par `ROADMAP.md` lui-même, pas sur une vérification d'imports que j'aurais effectuée fichier par fichier ce jour.

*Rapport produit en lecture seule — aucun fichier de `C:\OrionAI\` (hors `cowork_workspace\reports\`) n'a été modifié.*
