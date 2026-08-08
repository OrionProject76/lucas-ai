# Audit de nettoyage — Luca's AI (08-09/08/2026)

**Statut : inventaire uniquement, rien supprimé.** Chaque candidat ci-dessous
attend une validation explicite de Cyril, dans une session dédiée séparée,
avant toute suppression réelle.

**Méthode** : recherche d'imports Python (`grep` sur `from X import`/`import X`
pour chaque module suspect), croisement avec `git ls-files`/`git status
--porcelain --untracked-files=all`, lecture des sections `ROADMAP.md`
pertinentes pour confirmer ou infirmer un usage historique, comparaison de
taille/date pour les paires de fichiers qui se ressemblent. Rien n'est
avancé sans une vérification directe — pas une supposition sur le nom du
fichier seul.

---

## 1. Code orphelin (tracké en Git — récupérable via l'historique)

### `modules/stt_manager.py`

**Pourquoi il semble obsolète** : son propre en-tête se décrit comme « le
point d'entrée historique, celui que l'API appellera quand le S25 Ultra
enverra de l'audio » — mais ce n'est pas ce qui s'est produit. Le vrai
chemin mobile (branché le 02/08/2026, `api/server.py::websocket_endpoint`,
message WebSocket de type `"audio"`) appelle directement
`modules.stt_engine.STTEngine.transcribe_base64()`, sans jamais passer par
cette façade. Aujourd'hui, la seule référence restante à
`modules.stt_manager` dans tout le dépôt est son propre test
(`test_stt.py`) — vérifié par recherche d'imports, pas supposé.

**Contexte qui pourrait tromper** : un audit antérieur (`ROADMAP.md`,
section sur les doublons potentiels) affirmait explicitement que
`stt_engine.py`/`stt_manager.py` étaient « bien tous les deux utilisés ».
Cette affirmation datait d'avant le branchement du pont mobile du
02/08/2026 — elle a cessé d'être vraie à ce moment-là, sans qu'aucune note
ultérieure ne le signale. Une session de couverture de tests du 04/08/2026
a ajouté 4 tests à `stt_manager.py` (branches `is_available()`, chemin
mobile en échec) — cela couvre sa logique interne en isolation, ça ne
prouve pas qu'il est appelé par le reste de l'application.

**Recommandation** : supprimable si Cyril confirme que le pont mobile
STT restera sur `stt_engine.py` directement (aucune raison technique de
revenir à la façade n'a été trouvée). Tracké en Git — récupérable sans
perte si besoin.

---

## 2. Documentation dupliquée et périmée (trackée en Git)

### `cowork_workspace/CLAUDE.md`, `IDEAS.md`, `ROADMAP.md`, `VISION_LONG_TERME.md`

**Ce ne sont PAS des fichiers fantômes** — ils servent un vrai mécanisme :
`cowork_request_runner.ps1` les traite comme des documents de référence
protégés (`$Proteges = @("ROADMAP.md", "CLAUDE.md", "IDEAS.md",
"VISION_LONG_TERME.md")`, empreintés avant/après chaque traitement d'une
demande Cowork) — lus par les sessions Cowork (cloud, sans accès au poste
de Cyril), jamais censés être modifiés par elles. Ne pas les supprimer
sans remplacer le mécanisme.

**Ce qui est un vrai problème : ils sont périmés, et rien ne les
resynchronise.** Recherché explicitement (`grep` sur tout le dépôt pour un
script qui recopierait ces fichiers depuis la racine) — **aucun mécanisme
de synchronisation trouvé**. Comparaison directe :

| Fichier | Racine (référence) | `cowork_workspace/` (copie) | Écart |
|---|---|---|---|
| `IDEAS.md` | 1801 lignes, 09/08 | 1295 lignes, 07/08 | ~500 lignes manquantes — tout le catalogue `#97`–`#106` de cette session (RT-1 à RT-7, Groupes A à H, Lois d'Asimov) absent |
| `ROADMAP.md` | 8373 lignes, 09/08 | 7432 lignes, 07/08 | ~900 lignes manquantes — tout le Workspace E-1 (§5.68-§5.77), le Service Worker (§5.74), le style Terminal pro (§5.77) absents |
| `VISION_LONG_TERME.md` | 611 lignes, 08/08 | 553 lignes, 06/08 | Règles Absolues (§4.1bis) et Lois d'Asimov (§4.1ter) absentes |
| `CLAUDE.md` | 773 lignes, 06/08 | 773 lignes, 06/08 | **Identique** — celui-ci est à jour |

**Conséquence concrète** : une session Cowork qui consulte ces copies
aujourd'hui recevrait des instructions vieilles de plusieurs jours,
notamment sans les Règles Absolues, les Lois d'Asimov, ni le catalogue
`#97`+ — pas juste un détail cosmétique, une vraie divergence de contexte.

**Recommandation** : ce n'est pas un candidat à la suppression, c'est un
candidat à un **mécanisme de resynchronisation** (copie automatique
depuis la racine avant chaque traitement Cowork, par exemple) — à
discuter avec Cyril séparément de la liste de suppression proprement
dite.

---

## 3. Artefacts de build / outils périmés (non trackés, régénérables)

### `Lucas3D.exe` + `Lucas3D.console.exe` (racine)

Datés du **26/07/2026** — près de deux semaines d'ancienneté. Un export
Godot plus récent existe déjà : `build/Lucas3D.exe` +
`build/Lucas3D.pck`, datés du **07/08/2026**, correspondant très
probablement au « binaire exportable et reproductible » produit pendant
la session de surveillance/watchdog VRAM (`ROADMAP.md`, section
« Watchdog VRAM — fait le 07/08/2026 »). Non trackés en Git (déjà
ignorés via `Lucas3D.exe`/`Lucas3D.console.exe`/`*.pck` dans
`.gitignore`) — purement des artefacts de build, régénérables via
l'export Godot, aucune perte de code source en cas de suppression.
99 Mo + 92 Ko.

### `.aider.tags.cache.v4/`

Cache de l'outil **Aider** — un assistant de code IA différent de Claude
Code, jamais mentionné comme outil actif dans `CLAUDE.md`. Daté du
**25/07/2026**, avant même le renommage Orion→Luca's (29-30/07/2026).
Non tracké en Git. Vestige d'un essai d'outil antérieur à l'adoption de
Claude Code comme outil principal. 56 Ko.

### `tree_output.txt`, `tree_clean.txt`

Le `.gitignore` du projet les catégorise lui-même explicitement comme
« Sorties d'inspection ponctuelles » — non trackés par construction.
Datés du 01/08 et du 29/07/2026 : eux-mêmes périmés au regard de leur
propre nature (un instantané de `tree` vieux de plusieurs jours n'a plus
d'usage diagnostique).

### `modules/data/chromadb/` (dossier vide)

Une base ChromaDB **vide**, à l'intérieur de `modules/`, alors que la
structure documentée dans `CLAUDE.md` place la vraie base vectorielle
sous `data/chromadb/`. Le `.gitignore` du projet anticipe déjà ce
chemin (`modules/data/`) — quelqu'un avait déjà identifié le risque de
mauvais emplacement, sans jamais nettoyer le dossier lui-même resté sur
le disque. Vide, donc aucune donnée à perdre.

### `data/reports/` (dossier vide)

Vide, daté du 06/08/2026. La convention réellement utilisée dans tout le
projet (ROADMAP.md, `modules/workspace_manager.py::REPORTS_DIR`) est
`cowork_workspace/reports/`, pas `data/reports/`. Semble être une
tentative d'emplacement abandonnée avant que la convention actuelle ne
se stabilise.

---

## 4. Fichiers non trackés contenant des données personnelles (plus sensibles — jamais dans l'historique Git)

⚠️ Cette catégorie est différente des précédentes : rien ici ne peut être
récupéré via `git log`/`git checkout` en cas d'erreur — la seule copie
existe sur le disque de Cyril.

### `ORION_AI_Specifications_Completes_Claude.md`, `OrionAI_Analyse_Comparative_Kimi_x_Claude_v1_0.md`, `OrionAI_Vision_Claude_v1_0.md` (racine)

Le `.gitignore` du projet documente lui-même leur histoire : « Documents
de travail de Cyril déposés à la racine — jamais versionnés. Emportés
par erreur dans le commit `38a893c` (...), retirés du suivi juste
après. » Ils restent sur le disque (20 Ko + 20 Ko + 12 Ko), non trackés
depuis. Aucune indication qu'ils soient encore utiles au projet en l'état
— probablement des documents de travail antérieurs au noyau v1 actuel —
mais **contenu non lu par moi dans cet audit** (consigne du projet :
jamais afficher le contenu d'un fichier personnel sans vérifier sa
nature d'abord) : seule Cyril peut confirmer s'ils sont encore
pertinents ou entièrement caducs.

### `data/backups/lucas_memory_02082026_1855.db`, `data/backups/lucas_memory_05082026_0530.db`

Deux anciennes sauvegardes manuelles de la mémoire (conversations,
événements système réels de Cyril — données personnelles). Jamais
trackées en Git (`*.db` dans `.gitignore`, correctement). Un mécanisme
de sauvegarde **différent et plus récent** existe désormais, intégré au
code : `memory/memory_manager.py::_backup_if_migrating()` produit
automatiquement des fichiers `memory/lucas_memory.db.bak-<horodatage>`
à chaque migration de schéma (mécanisme construit le 08/08/2026, Brique
3). Ces deux fichiers dans `data/backups/` semblent être l'ancienne
convention manuelle, antérieure et maintenant redondante. 196 Ko au
total. **Contenu jamais ouvert** (même règle que ci-dessus) — à confirmer
par Cyril avant toute suppression, ce sont de vraies données.

### `data/tts_*.mp3` (86 fichiers, 3,1 Mo)

Clips vocaux synthétisés, qui devraient être supprimés automatiquement
après lecture selon le code lui-même (commentaire dans
`modules/voice_manager.py` : « chaque synthèse produit un fichier
unique... nettoyés après lecture en usage normal »). Leur présence en
nombre suggère des sessions interrompues avant lecture, ou un cas où le
nettoyage n'a pas eu lieu — pas un bug forcément grave, mais une
accumulation qui n'a pas vocation à durer. **Sensible à noter** : ces
fichiers audio reflètent potentiellement ce qui a été dit à voix haute à
Cyril — pas du code, du contenu réel. Jamais tracké en Git
(`data/tts_*.mp3` dans `.gitignore`).

---

## 5. Vérifié, mais volontairement écarté de la liste ci-dessus

Pour que cette liste reste un inventaire de vrais candidats, pas une
liste de tout ce qui a été regardé :

- **`core/reasoning_engine.py`, `core/memory_weighting.py`** — réellement
  câblés dans `core/lucas_core.py` (production, pas seulement testés).
  `reasoning_engine` est désactivé par défaut
  (`REASONING_ENGINE_ENABLED = False`, `config.py`) — un drapeau de
  fonctionnalité intentionnel documenté depuis le 03/08/2026, pas du
  code mort.
- **`modules/vram_watchdog.py`** — code réel, testé en conditions réelles
  (pas seulement mocké), pas du tout obsolète. Point distinct à vérifier
  avec Cyril, hors périmètre de cet audit de suppression : aucune tâche
  planifiée, script `.vbs`/`.ps1`, ni `lucas_daemon.py` ne semble le
  démarrer automatiquement (recherché explicitement, rien trouvé) — à
  clarifier s'il doit tourner en continu ou être lancé à la main avant
  chaque session Godot.
- **Dossiers fantômes `Fichier core/`/`Fichier ui/`** (incident historique
  documenté dans `CLAUDE.md`) — vérifiés absents du disque aujourd'hui,
  rien à signaler.
- **`cowork_workspace/ProjetWindows3D/`** — vérifié en cours d'audit : un
  vrai sous-projet actif, tracké en Git (commits `ffed773` et `e3d4dd7`,
  landés pendant la rédaction de ce rapport — travail concurrent sur ce
  même dépôt). Pas un candidat, mentionné seulement parce qu'il était
  passé par un état non tracké au moment précis où cet audit a
  commencé — corrigé ici pour ne pas laisser une observation devenue
  fausse entre-temps.
- **`core/ollama_reply.py`** — importé par `core/intent.py` et
  `core/local_llm.py`, activement utilisé malgré un nom qui pouvait
  faire penser à un doublon de `core/ollama_client.py`.
- **Scripts de démarrage** (`*_runner.ps1`, `start_*_hidden.vbs`) —
  chacun correspond à une tâche planifiée distincte (serveur API,
  Ollama, veille modèles, traitement Cowork) ; aucune redondance
  trouvée entre eux.

---

## Résumé pour décision

| Candidat | Tracké Git | Sensible | Action suggérée |
|---|---|---|---|
| `modules/stt_manager.py` | Oui | Non | Supprimer si confirmé orphelin |
| `cowork_workspace/{CLAUDE,IDEAS,ROADMAP,VISION_LONG_TERME}.md` | Oui | Non | **Resynchroniser**, pas supprimer |
| `Lucas3D.exe`, `Lucas3D.console.exe` (racine) | Non | Non | Supprimer (build périmé) |
| `.aider.tags.cache.v4/` | Non | Non | Supprimer (outil abandonné) |
| `tree_output.txt`, `tree_clean.txt` | Non | Non | Supprimer (déjà catégorisé jetable) |
| `modules/data/chromadb/` (vide) | Non | Non | Supprimer (mauvais emplacement, vide) |
| `data/reports/` (vide) | Non | Non | Supprimer (convention abandonnée) |
| 3 documents perso racine | Non | **Oui** | Décision de Cyril seul |
| `data/backups/*.db` | Non | **Oui** | Décision de Cyril seul |
| `data/tts_*.mp3` (86 fichiers) | Non | **Oui** (contenu vocal) | Décision de Cyril seul |

**Rien n'a été supprimé.** Cette liste attend la validation de Cyril,
dans une session dédiée séparée, comme demandé.
