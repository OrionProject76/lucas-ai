# SESSION LOG — Workspace Luca's, zone Sandbox (E-3), 09/08/2026

## Périmètre

Brief : `cowork_workspace/BRIEF_WORKSPACE_E3_SANDBOX.md`. Un seul module du
catalogue (`IDEAS.md` #102, Groupe E) : E-3, une zone où Luca's peut
proposer et exécuter du code en environnement isolé, visible et piloté par
Cyril — cinquième carte du Workspace, par-dessus le style "Terminal pro"
déjà livré (E-1, §5.77). Aucun autre module du catalogue (E-2 dataviz,
F-1 refonte PWA, etc.) n'a été touché.

## Étape préalable (brief §3) — vérifiée avant d'écrire du code

Recherché dans `modules/automation_manager.py`, `core/os_controller.py`,
`core/decision_engine.py`, et par mot-clé "sandbox"/"isolat" dans tout le
projet : aucun mécanisme d'exécution isolée n'existait. Seul résultat
pertinent, jamais implémenté : la règle elle-même
(`VISION_LONG_TERME.md` §4).

## Ce qui a été construit

- `modules/sandbox_runner.py` (nouveau) — bootstrap exécuté DANS le
  sous-processus isolé. Pose les gardes réseau/fichiers/processus AVANT
  tout `exec()` du code proposé.
- `modules/sandbox_manager.py` (nouveau) — orchestration : submit (jamais
  d'exécution) / execute / reject, cycle de vie pending→executed|rejected,
  timeout + `taskkill /F /T` sur dépassement.
- `memory/memory_manager.py` — table `sandbox_runs`, SCHEMA_VERSION 4→5.
- `modules/workspace_manager.py` — `CARD_IDS` +`"sandbox"`, `summary()`
  expose `sandbox_runs`.
- `api/server.py` — `POST /workspace/sandbox/{submit,execute,reject}`,
  même garde de jeton que le reste du Workspace, 400 propre sur
  `SandboxError`.
- `static/workspace.html` + `.css` + `.js` — cinquième carte, même style,
  formulaire + liste de propositions avec statut/sortie.
- `sandbox_workspace/` (nouveau répertoire, gitignoré sauf son
  `README.md`) — seule zone disque accessible au code sandboxé.
- `test_sandbox_manager.py` (nouveau, 21 tests, dont les gardes réseau/
  fichiers/processus/timeout en VRAI sous-processus) + 9 tests dans
  `test_server.py` + adaptations dans `test_workspace_manager.py` (5e carte).
- `ROADMAP.md` §5.78 — détail complet, y compris ce que l'isolation NE
  couvre PAS (honnêteté RT-2, pas une isolation OS).

## Vérifications réelles (pas seulement des tests mockés)

- Suite complète : 1573 passed, `ruff check .` propre, `mypy .` propre
  (128 fichiers).
- Serveur live (`LucasAPIServer`) redémarré — arbre `venv\Scripts\
  python.exe` → interpréteur réel retracé, `taskkill /F /T` sur la racine,
  relancé via la tâche planifiée. Migration de schéma confirmée en base
  réelle (`schema_version` = 5, backup automatique créé). Cycle
  submit→execute (réseau bloqué démontré : `socket.socket()` lève
  `PermissionError`, capturé et affiché) et submit→reject vérifié par
  `curl` contre le serveur HTTPS réel.
- Navigateur réel (Claude in Chrome), PC (1568px) et mobile (412px via
  `<iframe>`, même méthode que §5.77) : carte Sandbox affichée, formulaire
  utilisé réellement (frappe + clic, pas un appel direct), bouton Exécuter
  cliqué réellement, résultat affiché correctement aux deux largeurs.
  Captures à l'appui (voir conversation).

## État à la fin de la session

- Serveur live actif, nouveau PID confirmé via `Get-NetTCPConnection`.
- 3 propositions de test restent visibles dans le Workspace réel de Cyril
  (1 exécutée, 1 rejetée depuis les tests `curl`, 1 exécutée depuis le test
  navigateur) — contenu inoffensif (`print(...)`), laissé en place comme
  preuve visible plutôt que nettoyé, cohérent avec le reste du Workspace
  qui affiche déjà l'historique réel (actions, rapports).
- Commit + push effectués (voir `git log`).

## Friction rencontrée, sans rapport avec le code de ce chantier

Écran de Cyril à l'échelle Windows 300 % (déjà connu, voir l'ex-dossier
`cowork_workspace/ProjetWindows3D`, retiré sur sa demande le 09/08/2026).
`resize_window` de l'extension Chrome, appelé avec une largeur physique
proche ou au-delà de `window.screen.availWidth` (1280 à cette échelle), a
produit une fenêtre dégénérée plutôt qu'un redimensionnement ou une erreur
claire — récupéré en fermant l'onglet et en ouvrant un onglet neuf. À
garder en tête pour toute session future de test navigateur sur cette
machine.

## Pas encore fait

- Aucun générateur automatique de code côté Luca's (LLM qui proposerait
  lui-même un script) — cette session construit la zone d'exécution, pas
  un générateur. Cohérent avec le brief ("le code proposé par Luca's, s'il
  y en a").
- Pas de purge automatique des scripts `_proposition_*.py` accumulés dans
  `sandbox_workspace/` après exécution.
- `ctypes`/`multiprocessing` non bloqués par les gardes (documenté comme
  limite connue, pas un oubli — voir `modules/sandbox_runner.py`).
