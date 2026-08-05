# État des lieux — Luca's AI

**Date** : 04/08/2026, rédigé en fin de session autonome de nuit, **rafraîchi le
04/08/2026 (session suivante)** pour intégrer tout ce qui a été fait depuis — pas
recréé de zéro, la structure et la méthode d'origine restent inchangées.
**Objectif** : un document que quelqu'un qui n'a suivi aucune conversation peut lire en 10 minutes pour comprendre l'état réel du projet — pas un résumé de session, une carte.
**Méthode** : lecture directe du code (pas une compilation de `ROADMAP.md`) pour tous les fichiers de `core/`, `modules/`, `security/`, `api/`, `memory/`. `ui/` et les scripts `demos/` reposent davantage sur `ROADMAP.md` (couverture UI en particulier, mesurée fraîchement lors du rafraîchissement).
**État de la suite de tests au moment d'écrire** : **1021 tests, tous verts** (à la
rédaction initiale : 959).

---

## Ce qui a changé depuis la version initiale de ce rapport (résumé)

Sur décision explicite de Cyril, dans l'ordre :

1. **Les 4 éléments listés en §2/§4 de la version initiale ont été traités** :
   `ui/chat_widget.py` retiré (code mort confirmé) ; `modules/calculator.py`,
   `modules/weather_manager.py`, `modules/web_search.py` câblés dans le chat réel.
   Deux bugs réels trouvés au passage : `weather_manager.py` n'avait JAMAIS renvoyé
   de météo réelle (parsing `wttr.in` faux depuis l'écriture du module) ;
   `web_search.py` était cassé silencieusement (dépendance `duckduckgo-search`
   renommée en amont, tournait sans erreur mais ne renvoyait plus rien). Détail :
   `ROADMAP.md` §5.19.
2. **Audit "validation contre le vrai service" étendu** à `finance_manager.py`
   (déjà solide, gap honnête — aucun export réel de Cyril n'existe encore),
   `rag_manager.py` (solide, une vraie limite trouvée sur les requêtes courtes),
   `voice_manager.py` (déjà solide, reconfirmé), vision/OCR (solide sur 3 captures
   réelles variées). Détail : `ROADMAP.md` §5.20.
3. **Couverture UI PySide6 fermée** : 56%→87% (`avatar_widget.py` 48%→87%,
   `main_window.py` 64%→87%). Deux bugs réels trouvés en creusant : `repaint()`
   est un no-op silencieux sous `QT_QPA_PLATFORM=offscreen` sans `show()`
   préalable (45 tests croyaient exercer `paintEvent()`, 0% de couverture réelle
   malgré ça) ; la fixture de test UI lisait la VRAIE base de conversation de
   Cyril (contenu financier compris), jamais isolée. Les deux corrigés. Détail :
   `ROADMAP.md` §5.20.
4. **Modes AURA (Working/Deep Focus) validés en conditions réelles** : un bug
   réel trouvé (marqueurs à un seul mot "excel"/"word"/"terminal" en sous-chaîne
   nue, faux positifs sur des titres de fenêtre réels sans rapport avec le
   travail — "Wordle", "Terminal illness support group"...) et corrigé. Détail :
   `ROADMAP.md` §5.20.
5. **Seuil RAG** (`RAG_MAX_DISTANCE`) : Cyril tranche explicitement de le garder
   à 0,34 malgré la limite trouvée au point 2 — décision actée, pas un oubli.
6. **Nouvelle règle de sécurité** (`CLAUDE.md`) : plus jamais de P/Invoke Win32
   (`user32.dll` ou équivalent) pour manipuler des fenêtres en test, suite à un
   incident (fenêtre sensible capturée par accident, script bloqué par
   l'antivirus) pendant l'audit vision/OCR du point 2.

Le reste de ce document (carte du projet, dette technique, dépendances) est
réécrit ci-dessous pour refléter l'état réel actuel — plus une simple note en
tête, comme la version précédente de ce rafraîchissement le faisait.

---

## 1. Résumé exécutif

Luca's est un assistant local-first : un cœur Python (`core/`) orchestre des modules par domaine (`modules/`), une mémoire SQLite + RAG ChromaDB (`memory/`), des capteurs de sécurité en observation seule (`security/`), exposés par une API FastAPI unique (`api/`) à deux façades — une app PySide6 (`ui/`) et une PWA mobile (`static/`, pont S25 Ultra). Un avatar Godot 4 (`Lucas3D/`) existe en branche expérimentale, non intégré au flux principal.

Ce qui marche réellement aujourd'hui, validé en conditions réelles (pas seulement testé) : conversation texte locale/cloud routée par mots-clés + classifieur LLM, RAG sur les documents personnels de Cyril (39 documents, seuil recalibré, une vraie limite documentée sur les requêtes courtes — voir §2), calcul/météo/recherche web câblés dans le chat (`should_use_calculator`/`should_use_weather`/`should_use_websearch`), TTS à deux moteurs (edge_tts/Piper) avec garde de sécurité, capteurs de sécurité niveau 1 (observation, jamais d'action), pont mobile complet (chat, micro, caméra, TTS, HTTPS), modes AURA Working/Deep Focus (détection validée contre des scénarios réels et mockés).

Ce qui est construit mais délibérément **non câblé** à une vraie action (le fil conducteur des deux dernières sessions autonomes) : `core/decision_engine.py` (mécanisme + `ActionSpec` formalisé sur la vraie liste blanche, zéro action réelle dessus), les comportements des modes AURA (détection seule — filtrage de notifications, musique, compte à rebours toujours absents), la repondération confiance/provenance sur le RAG spécifiquement (câblée et no-op sur l'historique de conversation, jamais étendue à ChromaDB — schéma de métadonnées différent, chantier distinct non entrepris). Ce n'est pas de l'inachevé caché — c'est une frontière posée à chaque fois par la même règle : une nouvelle capacité d'action système attend un accord explicite de Cyril, jamais une extrapolation en session autonome.

---

## 2. Carte du projet

### `core/` — chef d'orchestre, décisions déterministes

| Fichier | Rôle | Statut réel |
|---|---|---|
| `lucas_core.py` | `LucasCore` — construit le prompt (`_build_messages()`), orchestre RAG/vision/finance/historique, appelle le LLM | **Fait, testé, câblé.** Cœur du système, le plus retravaillé du projet (plusieurs bugs réels corrigés en conditions réelles : dilution d'historique, auto-imitation de refus vision, RAG/finance muets). 96% de couverture. |
| `router.py` | `route()`/`is_sensitive()`/`should_use_rag()`/`should_use_vision()`/`should_use_finance()`/`route_voice()` — local vs cloud, quelle source consulter | **Fait, testé, câblé.** 100% de couverture. Sécurité = mots-clés déterministes toujours ; capacité (écran/documents) = délègue à `intent.py`. |
| `intent.py` | Classifieur LLM local (ÉCRAN/DOCUMENTS/AUCUN), avec repli mots-clés et cache | **Fait, testé, câblé.** 99%. Corpus de formulations réelles dans `test_intent.py`, enrichi à chaque échec observé. |
| `world_model.py` | Snapshot système (CPU/RAM/GPU/fenêtre active/heure réelle) | **Fait, testé, câblé.** 100%. |
| `aura_modes.py` | Détection Working/Deep Focus, déterministe | **Détection construite, testée, validée en conditions réelles, comportements NON câblés.** Bug réel trouvé et corrigé (marqueurs "excel"/"word"/"terminal" nus, faux positifs sur des titres réels type "Wordle"/"Terminal illness support group") — 20 tests. 6 des 8 modes AURA catalogués non construits (exclus, décision explicite). |
| `decision_engine.py` | Mécanisme lecture=auto/écriture=confirmation/exécution=confirmation+log | **Construit, testé, `ActionSpec` formalisé sur la vraie liste blanche — ZÉRO action réelle câblée dessus** (exclu explicitement : premier câblage réel attend un accord de Cyril). `automation_manager_actions()` génère les `ActionSpec` réels depuis `WHITELISTED_APPS`, `ILLUSTRATIVE_ACTIONS` séparé et étiqueté comme aspirationnel. |
| `memory_weighting.py` | Signale les souvenirs à faible confiance/expirés dans le prompt | **Construit, testé, câblé dans `_build_messages()`. No-op aujourd'hui** : rien n'écrit encore de confiance réduite. **Jamais étendu au RAG** (`modules/rag_manager.py`) — schéma de métadonnées ChromaDB différent (source/chunk/sha/periods, pas de confidence), chantier distinct jamais entrepris. |
| `dates.py` | Extraction de périodes (RAG daté — filtrage par mois/année) | **Fait, testé, câblé.** Corrige un bug réel de confusion de mois sur bulletins de paie. |
| `reasoning_engine.py` | Chain-of-thought v1 (plan avant réponse) | **Construit et testé, désactivé par défaut** (`REASONING_ENGINE_ENABLED=False`, config.py) — décision de Cyril, jamais réactivé en session autonome. |
| `local_llm.py` / `cloud_llm.py` / `ollama_client.py` / `llm_worker.py` / `text_utils.py` | Appels Ollama local, stub cloud, client HTTP bas niveau, worker Qt, normalisation de texte | **`local_llm.py`/`ollama_client.py`/`text_utils.py` : fait, testé, câblé (100%). `llm_worker.py` : testé (91%), câblé côté UI. `cloud_llm.py` : **stub intentionnel confirmé** — clé API cloud vide dans le `.env` réel de Cyril, zéro appel réel en usage observé.** |

### `modules/` — un fichier par domaine

| Fichier | Rôle | Statut réel |
|---|---|---|
| `rag_manager.py` | RAG ChromaDB — indexation, recherche hybride sémantique+date | **Fait, testé (97%), câblé.** Solide sur l'essentiel — validé en direct sur la vraie collection (39 documents) : « déclaration de revenus », « changement d'adresse », « attestation » retrouvent chacun leur vrai document, une question hors sujet ne retourne rien. **Vraie limite trouvée** : une requête COURTE (« mon CV ») rate le seuil de pertinence alors que le bon document est le meilleur candidat — une question complète (« Résume-moi mon CV ») passe. `RAG_MAX_DISTANCE` gardé à 0,34 (décision explicite de Cyril, pas un oubli). |
| `vision_manager.py` | Capture d'écran + description VLM (llava) | **Fait, testé (80%). VLM coupé** (`VLM_ENABLED=False`, config.py) — llava redimensionne en interne et ne lit pas le texte dense, d'où l'OCR en complément. |
| `ocr_engine.py` | Extraction de texte d'écran (RapidOCR, repli pytesseract) | **Fait, testé (100%), câblé.** Complète le VLM avec le texte exact. **Reconfirmé solide sur 3 captures réelles variées** (pas juste le cas déjà validé le 01/08) : texte connu à l'avance retrouvé mot pour mot, deux autres captures réelles non vides et cohérentes. Aucun bug. |
| `stt_engine.py` / `stt_manager.py` | Transcription audio (faster-whisper, repli openai-whisper) + façade tolérante | **Fait, testé (100%), câblé DEUX FOIS** : pont mobile (`api/server.py`) et desktop (bouton fichier, `ui/main_window.py`, ajouté le 04/08 — PAS un vrai micro, ce PC n'en a pas). |
| `voice_manager.py` | TTS à double moteur (edge_tts cloud / Piper local), routé par sensibilité | **Fait, testé (95%), câblé.** edge_tts par défaut, Piper forcé sur contenu sensible — jamais de repli cloud silencieux. **Reconfirmé solide** : edge_tts et Piper génèrent chacun un vrai fichier audio valide (MP3 25920 octets, sync word MPEG valide ; WAV 136748 octets, RIFF/WAVE valide, 3,10s réelles mesurées) — pas seulement "la fonction ne lève pas d'erreur". |
| `piper_engine.py` | Moteur TTS local (voix .onnx) | **Fait, testé (100%), câblé** (sous `voice_manager.py`). |
| `automation_manager.py` | Lancement d'appli sur liste blanche (chrome, calculatrice, notepad, explorer), sans confirmation | **Fait, testé (100%), câblé. SEUL mécanisme d'action système réel du projet.** `cmd`/PowerShell retirés de la liste (risque interpréteur). |
| `semantic_desktop.py` | Vue lecture seule sur les documents indexés (liste, apparentés, groupement par période) | **Fait, testé (100%), câblé.** Périmètre volontairement restreint — jamais de déplacement/renommage de fichier réel. |
| `finance_manager.py` + `finance_categorizer.py` | Import CSV bancaire + catégorisation (règles puis LLM local) | **Fait, testé (100%/97%), câblé** (`should_use_finance()`, `core/router.py`). CSV uniquement, jamais de connexion bancaire (règle 4). **Reconfirmé solide** : le code anticipe déjà les formats réels français (multi-délimiteurs, BOM, virgule décimale, débit/crédit séparés). **Gap honnête, pas un bug** : `data/finance/` n'existe même pas sur le disque — aucun export réel de Cyril n'a jamais été déposé, la validation contre un VRAI relevé reste impossible tant qu'il n'en fournit pas un. |
| `calculator.py` | Évaluation d'expressions arithmétiques sécurisée (pas d'`eval()` brut) | **Fait, testé, câblé** (`should_use_calculator()`, `core/router.py`) — le calcul est fait en Python, jamais deviné par le LLM. Validé en conditions réelles (« 45 + 32 » → 77). |
| `weather_manager.py` | Météo actuelle (wttr.in) | **Fait, testé, câblé** (`should_use_weather()`, `core/router.py`). **Bug réel corrigé** : le module n'avait JAMAIS renvoyé de météo réelle depuis son écriture (`?format=3` rend une seule ligne, pas quatre comme le supposait le parsing) — remplacé par un format personnalisé + détection HTTP. |
| `web_search.py` | Recherche web + filtre anti-fuite | **Fait, testé, câblé** (`should_use_websearch()`, déclenchement volontairement étroit). **Dépendance cassée trouvée et corrigée** : `duckduckgo-search` tournait sans erreur mais ne renvoyait plus aucun résultat (paquet renommé `ddgs` en amont). |

### `memory/` — mémoire de conversation + RAG

| Fichier | Rôle | Statut réel |
|---|---|---|
| `memory_manager.py` | Historique SQLite (`conversations`, `system_events`) — désormais confiance/provenance | **Fait, testé (100%), câblé.** Schéma étendu le 04/08 (source/date/confidence/last_validated/importance/expiration), migration additive validée sur une copie de la vraie base. |
| `index_documents.py` | CLI d'indexation batch (PDF/docx/txt, refus des fichiers de secrets, détection de logs) | **Fait, testé (99%), câblé.** Chaîne complète déposer→indexer→calibrer→interroger validée sur le corpus réel de Cyril. |

### `security/` — niveau 1, observation seule (jamais d'action)

| Fichier | Rôle | Statut réel |
|---|---|---|
| `guardian.py` | Détection process suspect (usurpation, sosie, répertoire volatil) | **Fait, testé (95%), câblé** (via `monitor.py`). |
| `privacy_shield.py` | Surveillance des connexions réseau sortantes | **Fait, testé (98%), câblé.** |
| `ransomware_watch.py` | Détection chiffrement massif par métadonnées (pas de lecture de contenu) | **Fait, testé (96%), câblé.** Analyse d'entropie explicitement écartée (décision de Cyril, IDEAS #84). |
| `persistence_watch.py` | Détection de nouveaux points de démarrage (registre, dossier Startup) | **Fait, testé (100%), câblé.** |
| `history.py` | Mémoire des comportements observés (« déjà vu ? »), période d'apprentissage | **Fait, testé (100%), câblé.** |
| `monitor.py` | Orchestre les 4 capteurs, déduplique, journalise | **Fait, testé (100%), câblé.** Appelé par `lucas_daemon.py`. |
| `status.py` | État affichable des capteurs (panneau des privilèges) | **Fait, testé (100%), câblé** (`api/server.py` → WebSocket). |
| `types.py` | `Finding`, niveaux de sévérité | **Fait, testé (100%).** |

### `api/` — API FastAPI unique

| Fichier | Rôle | Statut réel |
|---|---|---|
| `server.py` | `/chat`, `/history`, `/system`, `/documents...`, `/ws` (WebSocket chat+audio+image+pushes) | **Fait, testé (94%, fermé à date le 04/08), câblé.** Point d'entrée unique pour PySide6 (Godot potentiel) et la PWA mobile. |
| `protocol.py` | Vocabulaire WebSocket partagé (types de messages) | **Fait, testé (96%).** |

### `ui/` — interface PySide6

| Fichier | Rôle | Statut réel |
|---|---|---|
| `main_window.py` | Fenêtre principale — chat, avatar, TTS auto, bouton STT | **Fait, câblé, testé (87%, mesure fraîche).** `test_ui_workers.py` (36 tests) couvre les workers/threads, `send_message()` (le flux le plus emprunté de l'UI, jamais testé avant), `stop_generation()`/`closeEvent()` avec de vrais `QThread` bloqués. **Bug réel trouvé et corrigé** : la fixture de test construisait un vrai `LucasCore()` sur la VRAIE base de Cyril — `_load_history()` affichait donc son historique réel (financier compris) dans les tests depuis 25+ tests jamais remarqués. Isolée sur base temporaire. |
| `avatar_widget.py` | Avatar 2D animé (5 modes de présence, halo, transitions) | **Fait, câblé, testé (87%, mesure fraîche — était 48%).** `test_avatar.py`, 51 tests. **Bug réel trouvé et corrigé** : `repaint()` est un no-op silencieux sous `QT_QPA_PLATFORM=offscreen` sans `show()` préalable — les 45 tests précédents croyaient exercer `paintEvent()` via `repaint()`, 0% de couverture réelle malgré ça (vérifié par instrumentation directe). |
| `chat_widget.py` | — | **Retiré** (04/08/2026) : code mort confirmé (`ChatWidget` jamais importé nulle part hors sa propre définition), `git rm`. |

### Racine et daemon

| Fichier | Rôle | Statut réel |
|---|---|---|
| `main.py` | Point d'entrée FastAPI + PySide6 | Support de validation réelle répété tout au long du projet. |
| `config.py` | Configuration centralisée (tous les seuils/budgets/interrupteurs) | Chaque constante a une justification écrite en commentaire, la plupart mesurées en conditions réelles. |
| `lucas_daemon.py` | Daemon 24/7 — orchestre `security.monitor.SecurityMonitor`, rapports planifiés | Câblé, tourne en tâche de fond. |

### Hors périmètre de cette relecture (voir l'audit du 03/08 pour le détail)
`demos/*.py` (scripts manuels de calibrage/démo), `Lucas3D/` (GDScript, pas Python), `static/js/*` (PWA).

---

## 3. Architecture actuelle vs `VISION_LONG_TERME.md`

| Pilier / brique de la vision | Construit aujourd'hui | Prévu, non commencé |
|---|---|---|
| **Pilier 1 — Visuel spatialisé** (bureau sémantique 3D, avatar holographique, HUD orbital) | Avatar 2D (`avatar_widget.py`) intégré et animé ; `semantic_desktop.py` en lecture seule (liste/apparentés/groupement, pas de visualisation 3D) | Godot 4 (`Lucas3D/`) en branche expérimentale, jamais raccordé au flux principal ; bureau 3D spatialisé ; barre Luca's (remplace la taskbar) |
| **Pilier 2 — Cognition modulaire** (perception/exécution/raisonnement séparés, mémoire 3 niveaux, decision engine) | Architecture modulaire déjà en place (`core/`, `modules/`, un seul flux de décision Python) ; `reasoning_engine.py` construit (désactivé) ; `decision_engine.py` construit, `ActionSpec` formalisé sur la vraie liste blanche (aucune action câblée) ; mémoire enrichie confiance/provenance (câblée sur l'historique de conversation, no-op aujourd'hui, jamais étendue au RAG) | Mémoire procédurale explicite ; auto-analyse nocturne périodique ; module perceptif continu (aujourd'hui : capture à la demande, pas en continu) ; repondération RAG (schéma ChromaDB distinct, jamais entrepris) |
| **Pilier 3 — Corps étendu (PC + S25 Ultra)** | Pont mobile complet et validé (chat, micro, caméra, TTS, HTTPS) ; STT partagé entre les deux faces (mobile + desktop, ajouté 04/08) | — cette brique est la plus achevée du projet |
| **§4 — Sécurité : liberté conditionnée à la protection** | Guardian + Privacy Shield + Ransomware Watch + Persistence Watch tous construits, testés, câblés (niveau 1 complet) | Niveau 2 (watcher entropie réel) — décision de principe actée, pas construite. Extension des libertés d'action de Luca's conditionnée à la maturité de ces capteurs — la condition existe, personne ne l'a encore invoquée pour élargir quoi que ce soit |
| **Modes AURA (S5)** | Working + Deep Focus : détection seule, validée en conditions réelles (1 bug de faux positifs trouvé et corrigé) | Comportements réels (notifs filtrées, musique, compte à rebours) ; 6 autres modes (Creating, Meeting, Gaming, Entertainment, Learning, Social) |
| **OS Controller (S6)** | `automation_manager.py` (lancement d'appli) ; `decision_engine.py` (mécanisme, pas d'action) | Manipulation réelle de fichiers, actions contextuelles, tout ce que la liste blanche pourrait couvrir au-delà du lancement d'appli |
| **HERMES + JARVIS (addendum 03/08)** | Rien — direction actée sur le principe uniquement | Tout — explicitement gelé jusqu'à une session supervisée dédiée (CLAUDE.md, précision du 01/08 sur la règle 12) |

**Lecture d'ensemble** : le pilier le plus proche de la vision est le Pilier 3 (pont mobile). Le plus en retard est le Pilier 1 (le visuel spatialisé reste un avatar 2D, pas l'environnement 3D décrit). Le Pilier 2 a une fondation solide et délibérément sous-exploitée — c'est le fil rouge de la session du 04/08 : construire le mécanisme, ne jamais lui donner de pouvoir réel sans un accord explicite.

---

## 4. Dette technique connue

1. **`ui/chat_widget.py` était du code mort** (trouvé le 04/08) — **retiré** (`git rm`), plus rien à surveiller ici.

2. **Écart de documentation trouvé et corrigé le 04/08** : `core/decision_engine.py` avait été construit en supposant qu'une liste blanche catégorisée ("volume, luminosité, presse-papier, lancement d'appli, capture d'écran") existait déjà dans la documentation. Vérifié : elle n'existait pas. Corrigé en séparant `automation_manager_actions()` (réel, généré depuis la vraie liste blanche, formalisé en `ActionSpec`) d'`ILLUSTRATIVE_ACTIONS` (aspirationnel, étiqueté comme tel). Voir `CLAUDE.md`, section "Liberté conditionnée à la protection".

3. **Trois modules autrefois orphelins sont désormais câblés** : `modules/calculator.py`, `modules/weather_manager.py`, `modules/web_search.py` — voir §2. Deux bugs réels trouvés et corrigés au passage (parsing wttr.in jamais correct ; dépendance `duckduckgo-search` cassée silencieusement).

4. **Dépréciations PySide6 relevées en testant** (`ui/avatar_widget.py`, trouvées le 04/08, **toujours non corrigées** — hors périmètre d'une session de tests) : `event.pos()` (ligne 278) et le constructeur `QMouseEvent(type, pos, button, buttons, modifiers)` sont dépréciés au profit de `event.position()`. Sans effet aujourd'hui (avertissement, pas erreur).

5. **Outillage `pytest-cov` — résolu.** L'instabilité notée initialement (`ImportError: cannot load module more than once per process`) ne s'est pas reproduite dans un processus Python frais lors du rafraîchissement de ce rapport : mesure de couverture UI obtenue sans problème (87%/87%, voir §2). Confirme l'hypothèse déjà posée : un redémarrage de processus suffisait.

6. **`repaint()` est un no-op silencieux sous `QT_QPA_PLATFORM=offscreen` sans `show()` préalable** (trouvé en creusant pourquoi la couverture de `paintEvent()` restait à 0% malgré des dizaines de tests qui appelaient `repaint()`). Corrigé (`show()` + `processEvents()` dans la fixture) : couverture 48%→87%. Même famille que les bugs "tests verts, comportement jamais réel" trouvés cette nuit sur `weather_manager.py`/`web_search.py`.

7. **La fixture de test UI (`app_window`) lisait la VRAIE base de conversation de Cyril** (`memory/lucas_memory.db`), affichant son historique réel — financier compris — dans `chat_history` depuis 25+ tests préexistants, jamais remarqué faute d'assertion dessus. Corrigée : isolée sur `tmp_path`.

8. **Marqueurs à un seul mot dans `core/aura_modes.py`** ("excel", "word", "terminal" nus) déclenchaient WORKING sur des titres de fenêtre réels et courants sans rapport avec le travail ("Wordle", "Word Search Puzzle", "Terminal illness support group"). Corrigé par désambiguïsation (`" - excel"`, `" - word"`, retrait de `"terminal"` nu).

9. **RAG : requêtes courtes sous le seuil de pertinence** — voir §2. Décision de Cyril : `RAG_MAX_DISTANCE` reste à 0,34, pas un défaut à corriger.

10. **Nouvelle règle de sécurité** (`CLAUDE.md`) : plus de P/Invoke Win32 (`user32.dll`) pour manipuler des fenêtres en test, suite à un incident réel (fenêtre sensible capturée par accident pendant l'audit vision/OCR, script bloqué par l'antivirus — Bitdefender, pas Windows Defender, confirmé par requête directe — avant toute exécution). Aucune autre conséquence : ni exécution partielle, ni action au-delà du blocage.

11. **Couverture résiduelle acceptée** (lignes isolées, même catégorie partout : blocs `__main__`, imports de compatibilité, branches défensives rares) : `core/dates.py`, `core/lucas_core.py`, `modules/finance_manager.py`, `modules/rag_manager.py`, `security/guardian.py`, `security/ransomware_watch.py`, `ui/avatar_widget.py` (bloc `__main__`), `ui/main_window.py` (gardes d'import optionnelles, `stop_generation()`/`closeEvent()` sous conditions `isRunning()` désormais couvertes, quelques branches uniques restantes) — non poursuivi, rendements décroissants.

---

## 5. Dépendances et points de couplage entre modules

- **`STTEngine` (modules/stt_engine.py) est partagé entre DEUX chemins réels** : `api/server.py` (pont mobile, instance de module `_stt_engine`) et `ui/main_window.py` (bouton fichier desktop, instance de module `_stt_engine` distincte mais même classe). Jamais un second pipeline de transcription — les deux passent par le même moteur, la même logique de cache.
- **`core/world_model.get_snapshot()` est consommé par** : `core/lucas_core.py` (contexte du prompt), `api/server.py` (`/system`, push WebSocket), `core/aura_modes.py` (détection Working, via le champ `active_window`).
- **`security/history.BehaviourHistory` est PARTAGÉE entre deux capteurs** : `PrivacyShield` (premier contact réseau) et `PersistenceWatch` (nouvelle entrée de démarrage) — une seule mémoire des comportements, injectée aux deux.
- **`core/intent.classify()` est le point de convergence unique** pour "écran ou documents" — `should_use_vision()` et `should_use_rag()` (`core/router.py`) délèguent tous les deux au même appel, garantissant l'exclusivité mutuelle des deux labels (plus de collision RAG/vision possible par construction).
- **`core/decision_engine.py` ne dépend d'aucun autre module métier** (par conception) mais `automation_manager_actions()` LIT `modules.automation_manager.WHITELISTED_APPS` à chaque appel — un couplage de LECTURE SEULE délibéré, pour ne jamais pouvoir dériver de la vraie liste blanche.
- **`memory/memory_manager.MemoryManager` est consommée par** quasiment tout : `core/lucas_core.py`, `api/server.py`, `ui/main_window.py`, `lucas_daemon.py` (indirectement via `security/monitor.py`'s `log_event`). Chaque point d'accès recrée sa propre instance (jamais partagée entre threads) à cause de la contrainte SQLite/thread déjà documentée dans `CLAUDE.md`.
- **`modules/rag_manager.RAGManager` est consommée par** `core/lucas_core.py` (RAG dans le prompt), `memory/index_documents.py` (indexation), `modules/semantic_desktop.py` (lecture seule des mêmes données).
- **Aucun module de `security/` n'importe `core/lucas_core.py`** (contrainte architecturale explicite, pour éviter un cycle) — tous reçoivent `log_event` par injection.

---

## 6. Question ouverte

**Le pont audio partagé (`STTEngine`) a maintenant deux appelants réels avec des contraintes très différentes** — le mobile reçoit de l'audio court, fréquent, en direct ; le desktop transcrit un fichier déjà enregistré, potentiellement long, à la demande. `STT_CACHE_SIZE` (modules/stt_engine.py) borne un cache commun aux deux usages avec la même taille. Si le desktop devient un usage réel (mémos vocaux longs, par exemple), la clé de cache (le chemin du fichier) et la taille du cache resteront pertinentes pour lui — mais rien n'a été mesuré pour ce second profil d'usage, seulement pour le mobile. **Est-ce que ce cache mérite un réglage séparé par appelant avant que le bouton desktop ne devienne un usage quotidien, ou est-ce prématuré tant qu'il reste un usage occasionnel ?** Pas une urgence — juste un point où l'architecture actuelle (un seul moteur, une seule config) pourrait un jour gêner un usage que la vision (Pilier 3) encourage explicitement à développer.

---

*Rapport produit en session autonome, rafraîchi en session suivante (même jour) sur demande explicite de Cyril. Code non modifié par la rédaction de ce document — seule sa lecture (et l'exécution de la suite de tests pour les pourcentages de couverture) a servi de base.*
