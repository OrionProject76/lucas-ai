# ROADMAP.md — Plan d'action Luca's AI (ex-OrionAI)

Référence croisée : voir `IDEAS.md` pour le détail complet de chaque fonctionnalité citée ici.

> **Mise à jour du 30/07/2026** : S1 (Cerveau solide — FastAPI unique) est officiellement validé de bout en bout. Prochaine étape : S2 (Mémoire enrichie, RAG, TTS, Finance CSV).
>
> **Renommage acté** : le projet s'appelle désormais **Luca's** (ex-Orion). Le renommage technique complet (titre fenêtre, prompts système, nom de dossier) est différé — pas urgent, sera fait une fois le socle S2-S3 stabilisé. Voir section 6.

---

## 1. État actuel (au 30/07/2026)

### ✅ Modules validés et testés en conditions réelles
1. Chat avec streaming QThread (UI PySide6)
2. Mémoire persistante SQLite (`memory/orion_memory.db`) — confirmée comme seule source de vérité
3. FastAPI unique (`api/server.py` v0.2) — **testé de bout en bout aujourd'hui** :
   - `GET /status` ✅
   - `GET /system` ✅ (World Model v1 : CPU, RAM, fenêtre active via psutil + pywin32)
   - `POST /chat` ✅ (connecté à `OrionCore.ask()` → Ollama → réponse réelle, plus de stub)
   - `WS /ws` — endpoint créé, protocole minimal état/parole, **pas encore testé avec un vrai client** (Godot/mobile viendront en S6/S5)
4. Modèle LLM confirmé en usage réel : `qwen2.5:7b` (via Ollama)
5. Avatar 2D QPainter (v2)

### ⚠️ Statut réel à clarifier (non re-testés depuis l'audit initial)
- `modules/finance_manager.py`, `rag_manager.py`, `vision_manager.py`, `weather_manager.py`, `automation_manager.py`, `web_search.py` — à tester lors de S2/S3
- `Orion3D.exe` (Godot) — visage/fenêtre transparente fonctionne visuellement, mais `orion3d_bridge.py` fait uniquement écho, pas connecté à Ollama/OrionCore

### 🟡 Godot 4 — toujours en branche expérimentale (non bloquant)
Reclassé en Phase 6 (S5-S6), branche `experimental/godot-avatar`. Ne bloque pas la release.

---

## 2. Étape immédiate — Phase 2 : Mémoire enrichie & Finance (S2)

**Objectif : enrichir le cerveau maintenant qu'il répond correctement.**

| Tâche | Détail |
|---|---|
| Mémoire enrichie | Contexte conversation + events système (World Model) injectés dans le prompt |
| RAG documents personnels | ✅ **Fait et validé en conditions réelles (01/08/2026).** 39 documents de Cyril indexés, 229 morceaux. Point d'entrée `memory/index_documents.py` (relançable sans risque), lecture `.pdf` / `.docx` / texte, recherche hybride sémantique + date, seuil de pertinence calibré sur le corpus réel. Voir l'encadré ci-dessous. |
| TTS intégré au chat | Bouton + lecture auto dans l'UI PySide6, brancher `modules/voice_manager.py` (à re-tester) |
| Finance CSV | Import + catégorisation, dashboard simple (MVP, pas d'API bancaire — règle actée) |

#### ✅ RAG documents personnels — terminé le 01/08/2026

**Chaîne complète** : déposer → indexer → calibrer → interroger.

```
venv\Scripts\python.exe -m memory.index_documents "C:/Users/PC/Documents"
venv\Scripts\python.exe demos\calibrate_rag.py
```

**Validé via `main.py`**, pas seulement par des tests :

| Question | Résultat |
|---|---|
| « Résume-moi mon CV » | cite `Cv2026_DE-As`, contenu réel |
| « Quel était mon salaire net en juillet 2025 ? » | **1647.68 €**, depuis le bon bulletin |
| « Et en décembre 2025 ? » *(ellipse)* | rattachée au tour précédent, bon bulletin |
| « Quel était mon salaire en juillet 2024 ? » | « aucun document correspondant » — **rien d'inventé** |
| « Quelle est la capitale de l'Australie ? » *(témoin)* | aucun RAG déclenché |

**Réglages calibrés sur le corpus réel**, pas devinés : `RAG_MAX_DISTANCE`
(0,33), `CHUNK_SIZE`, `CHUNK_OVERLAP`, `SOURCE_HISTORY_MESSAGES`. Tout
changement du format d'indexation incrémente `RAGManager._FORMAT_VERSION`,
ce qui force la réindexation — sinon la base resterait silencieusement à
l'ancien format.

**Reste ouvert** : les documents scannés (cartes d'identité, certains
contrats) n'ont aucune couche texte et sont refusés avec leur motif. Les
passer par `modules/ocr_engine.py`, déjà présent pour l'écran, est une
piste v1.1.

**Prérequis avant de commencer S2 :** vérifier qu'Ollama tourne sans doublon de process (voir section 5 — point de vigilance infra).

---

## 3. Jalons futurs

| Phase | Semaine | Focus | Statut |
|---|---|---|---|
| **Phase 0 — Audit** | S0 | Nettoyage, inventaire | ✅ Fait (avec incident de suppression accidentelle résolu — voir CLAUDE.md) |
| **Phase 1 — Cerveau solide** | S1 | FastAPI unique + World Model | ✅ **Fait et validé aujourd'hui** |
| **Phase 2 — Mémoire & Finance** | S2 | RAG, TTS, Finance CSV | ✅ Fait le 01/08 — reste la validation TTS à l'oreille dans l'UI |
| **Phase 3 — Vision & Voix** | S3-S4 | VLM écran, Avatar QPainter V3, 5 modes de présence | 🟡 En cours — VLM écran ✅, 5 modes de présence ✅ |
| **Phase 4 — Expansion** | S5-S6 | PWA mobile, sync, Godot 4 V1 (branche expérimentale) | À venir |
| **Phase 5 — Polish** | S7-S8 | Sécurité finale, packaging, release v1.0 | À venir |

### État détaillé de la Phase 3 (au 01/08/2026)

| Brique | État |
|---|---|
| **Vision écran (OCR)** | ✅ **Fait et validé en conditions réelles (01/08/2026)** — en OCR seul, voir l'encadré ci-dessous. La capture est lue par RapidOCR (CPU) ; le VLM est coupé. Le déclencheur n'est plus une liste de mots-clés mais `core/intent.py`. Vérifié via `main.py` : « c'est écrit quoi ? » et « une synthèse d'un document sur mon écran » citent le texte réellement affiché. Forcé en local : ce qui est lu à l'écran ne part jamais au cloud. |
| **5 modes de présence** | ✅ Fait. `IDLE`, `THINKING`, `SPEAKING`, `WATCHING`, `LISTENING` dans `ui/avatar_widget.py`. `WATCHING` sert de témoin de capture, comme la LED d'une webcam. `LISTENING` reste inactif faute de micro. |
| **Avatar QPainter V3** | 🟡 Partiel. Le rendu a été restauré et fiabilisé (voir §6), les modes sont câblés sur le comportement réel. Une refonte esthétique complète reste possible si Cyril la souhaite. |
| **STT** | ⛔ Bloqué par le matériel — moteur écrit, voir ci-dessous. |

#### 🟡 Vision v1.0 = OCR seul. Le VLM est suspendu, pas abandonné.

**Décision de Cyril, 01/08/2026.** `VLM_ENABLED = False` dans `config.py`.

**Motif** : llava ne se trompe pas, il **fabrique**. Quatre observations
réelles sur quatre captures : une erreur `docker.sock`, un `mount /dev/sda6`,
un « je ne peux pas décrire l'image », et un traceback Python complet —
`TypeError: 'int' object is not iterable`, fichier et numéro de ligne — suivi
de trois paragraphes de solution pour un bug inexistant. Aucune de ces phrases
n'était à l'écran. Sur les trois essais réels finaux, sa contribution a dégradé
deux réponses et n'en a amélioré aucune ; le faux traceback contaminait jusqu'à
la réponse voisine.

> Une vision absente se voit. Une vision fausse se croit.

**⚠️ Ce qu'on perd, et qu'il faut assumer** : Luca's **ne sait plus dire quelle
application est ouverte ni comment l'écran est disposé**. Elle lit le texte,
elle ne décrit plus la scène. Sur un écran sans texte — image, vidéo,
graphique — elle n'a plus rien à dire. C'est la moitié de la promesse de la
couche perception (`VISION_LONG_TERME.md` §2), mise en pause faute d'un modèle
fiable. Ce n'est pas une suppression discrète de fonctionnalité : c'est un
compromis, et il est ici pour être relu.

**➜ v1.1 — rétablir la description visuelle avec `internvl2`**, déjà prévu au
tableau des modèles de `CLAUDE.md`. Point de vigilance inchangé : la contention
GPU avec Ollama (`VISION_LONG_TERME.md` §3) — c'est précisément ce qui avait
fait préférer llava. **Rien n'a été supprimé** : le code des deux sources est
intact, les tests du chemin VLM tournent toujours (`_fake_vision` l'active
explicitement), et `VLM_ENABLED = True` + `VLM_MODEL = "internvl2"` suffisent à
le réactiver.

#### 🟢 Session autonome du 02/08/2026 — avatar Godot

Quatre défauts trouvés **en mesurant**, tous invisibles au simple coup d'œil :

| défaut | comment il a été trouvé | correction |
|---|---|---|
| **Bouche invisible** (0 pixel clair en `idle`, 0 en `watching`, 6 en `speaking`) | planche de contrôle des 4 états, dérive figée | z 2,2 → 2,45. **Géométrique, pas lumineux** — monter la luminosité de 0,5 à 0,75 faisait passer le compte de 6747 à 6758 |
| **Yeux asymétriques** — le gauche systématiquement plus gros | même planche | leur z est calculé sur l'ellipsoïde à chaque image. Écart 5,1 % en `idle`, 7,7 % en `speaking` |
| **`watching` jamais émis** vers Godot | vérification que les états se déclenchent en usage réel | `api/server.py` décide de l'état **avant** `orion.ask()` |
| **Inclinaison imperceptible** (médiane 0,76°, p90 1,72°) | mesure sur 10 min simulées | `LEAN_GAIN` 0,035 → 0,09 → p90 4,42° |

⚠️ Le plus important est le troisième. **`WATCHING` est le témoin de capture
d'écran** — l'équivalent de la LED d'une webcam, acté comme signal de
confidentialité. L'UI PySide6 le respectait ; le chemin Godot ne le
respectait pas. Un avatar 3D qui regarde l'écran sans le montrer, c'est
exactement ce que le témoin existe pour empêcher.

**Décisions prises seul, réversibles, à valider :** luminosité de la bouche
à 0,4 (à 0,75 elle écrasait les yeux, or la hiérarchie du visage doit leur
revenir) et `LEAN_GAIN` à 0,09.

**Outil conservé** : `Orion3D/scripts/_expr.gd` produit la planche des
quatre expressions. Retiré de `main.tscn`, mode d'emploi en tête du
fichier. C'est lui qui a trouvé les deux premiers défauts.

#### ⛔ Click-through : bloqué par une limite de Godot 4.7 sur Windows

**État acté le 02/08/2026 : on laisse en l'état, le correctif réel est différé.**

Un compagnon de bureau doit laisser passer les clics là où il n'y a rien.
Aujourd'hui l'overlay **capte tous les clics de l'écran**. Les deux voies
accessibles depuis GDScript ont été essayées et **mesurées** :

| voie | résultat mesuré |
|---|---|
| `window_set_mouse_passthrough(polygone)` | les clics traversent, **mais le rendu est découpé** — avec un trou de test commençant à x=1200, la tête de l'avatar apparaît tranchée verticalement à x=1200 exactement |
| `WINDOW_FLAG_MOUSE_PASSTHROUGH` | **sans effet** — la bascule s'exécute bien (journalisée : `true` → `false` sur le HUD → `true` au centre) mais `GWL_EXSTYLE` ne change jamais et `WS_EX_TRANSPARENT` n'est jamais posé |

L'état retenu privilégie **le rendu** : tout s'affiche, la fenêtre capte
les clics. Acceptable tant que Godot se lance et se ferme pendant le
travail sur l'apparence ; **inacceptable pour un usage continu**.

**➜ Le correctif : une petite GDExtension qui pose `WS_EX_TRANSPARENT`.**
La politique est déjà écrite et vérifiée — `window_manager._dans_hud()`
décrit quelles zones interceptent, et `WindowFromPoint` sur huit points
sert de test. Seul le mécanisme manque. Ne pas supprimer
`_appliquer_traverse()` en croyant nettoyer du code mort.

⚠️ Deux constantes y sont mesurées et non devinées : `TASKBAR_RESERVED`
(144 px — `screen_get_usable_rect()` rend l'écran entier sur cette
machine, vérifié en l'affichant) et les bords du HUD. À revoir si Cyril
change son échelle d'affichage.

#### 🔴 Bug de fond ouvert (02/08/2026) — Godot se ferme ou gèle spontanément, cause non identifiée

Sur cette machine, `Godot.exe --path Orion3D` (lancé depuis l'éditeur, hors export) a **quatre fois** quitté ou gelé de lui-même après quelques minutes d'exécution, **sans aucune trace** :

- Aucune ligne supplémentaire dans les logs (stdout/stderr redirigés) — le process s'arrête net après « Connecte a Orion Backend », rien après.
- Aucune entrée dans le journal d'événements Windows (`Get-WinEvent -LogName Application`) — ni « Application Error » (crash), ni « Application Hang » (gel). Sur les deux occurrences où la fermeture a été observée en direct par Cyril, une fois c'était une disparition silencieuse (processus absent de `tasklist`), une fois un gel visible (icône grisée « ne répond pas » dans la barre des tâches, tuée manuellement par `taskkill /F /IM Godot.exe`).
- Reproduit avec au moins deux versions différentes de `window_manager.gd` (avant et après le correctif de zone HUD), donc **pas causé par le contenu du script à lui seul** — mais la dernière occurrence (le gel) a suivi de près un changement touchant `window_set_mouse_passthrough()`, donc un lien n'est pas exclu non plus.

**Hypothèse la plus concrète, non vérifiée** : `window_set_mouse_passthrough()` a été appelé avec un polygone **dégénéré** — trois points strictement identiques, hors écran (`_region_totalement_hors_ecran()` dans `window_manager.gd`, ajouté puis remplacé le 02/08/2026). Un polygone à aire nulle avec des sommets confondus est un cas limite classique pour un algorithme de géométrie (triangulation, construction de région Win32 `SetWindowRgn`) : plusieurs implémentations bouclent indéfiniment ou restent bloquées sur une comparaison qui ne se résout jamais (arêtes de longueur nulle). C'est un candidat plausible pour un **gel** (le thread principal ne rend plus la main à la boucle de messages Windows), par opposition à un crash qui laisserait une trace.

Cette hypothèse n'explique pas a elle seule les disparitions silencieuses observées **avant** ce changement (avec l'ancien code, qui n'appelait jamais `window_set_mouse_passthrough`) — il y a donc peut-être **deux causes distinctes** : une instabilité de fond (pilote Vulkan/RTX 5080, ou autre) indépendante du code, et un risque de gel spécifique aux polygones dégénérés.

**Avant de retenter un correctif de polygone dégénéré** : remplacer les trois points identiques par un vrai (micro-)polygone non dégénéré mais toujours hors écran (ex. trois sommets distincts autour de (-10,-10), (-9,-10), (-10,-9)), pour éliminer cette piste sans revenir sur la décision de fond.

**État actuel, choisi par Cyril le 02/08/2026** : rester sur le comportement le plus sûr — fenêtre invisible mais qui ne bloque jamais le bureau (`_appliquer_passthrough_total()`) — plutôt que d'itérer sans supervision directe. Le chantier avatar/HUD Godot est **en pause** jusqu'à ce que Cyril supervise en direct le prochain essai visuel. Ne pas relancer Godot pour des tests automatisés sans lui tant que ce point n'est pas rouvert.

⚠️ **Attention en reprenant la Phase 3** : « 5 modes de présence » n'était défini nulle part. Il s'agit des états de Luca's elle-même, **à ne pas confondre avec les 8 « modes AURA »** d'`IDEAS.md` (Working, Gaming, Meeting…), qui sont des contextes d'activité de Cyril et relèvent de S5.

### ⚠️ Ce qui dépend du micro et de la caméra ne peut pas être fait avant le mobile

`IDEAS.md` #69 et `VISION_LONG_TERME.md` §2 Pilier 3 l'actent : **le PC n'a ni micro ni webcam, et c'est définitif.** Tout ce qui en dépend passe obligatoirement par le S25 Ultra, donc par le pont mobile — la Phase 4 de ce tableau.

Trois missions sont concernées, alors qu'elles sont annoncées en S1 dans la liste des priorités de `CLAUDE.md` :

| Mission | Dépend de | Faisable à partir de |
|---|---|---|
| `mission_03_audio_watcher` | micro | Phase 4 (pont mobile) |
| `mission_04_webcam_watcher` | caméra | Phase 4 (pont mobile) |
| `mission_10_stt_engine` | micro | Phase 4 — moteur déjà écrit, voir ci-dessous |

**Ne pas rebuter dessus** : les prendre avant le pont produit du code correct que rien ne peut alimenter ni valider en usage réel.

Le moteur STT (`modules/stt_engine.py`) est **déjà écrit et testé**, commité le 01/08 comme socle. Il ne capte rien : il transcrit ce qu'on lui donne, et attend que le mobile lui envoie de l'audio. **Il ne compte pas comme une avancée de Phase 3.**

> **Note de numérotation.** Ce tableau place le pont mobile en **Phase 4** (semaines S5-S6), tandis que la section « Priorités de Développement » de `CLAUDE.md` situe le « Mobile Bridge » en S7. Les commentaires de code écrits le 01/08 (`config.py`, `README_INSTALL.md`, `stt_engine.py`) parlent de « Phase 5 », en reprenant le libellé de semaine. Les trois désignent la même étape : **l'arrivée du S25 Ultra**. À harmoniser lors d'une passe dédiée sur la numérotation.

---

## 4. Principe directeur

> **"Cerveau solide d'abord, visage beau ensuite. Mais le visage ne part jamais."**

Architecture serveur validée aujourd'hui : une seule API FastAPI, `/ws` unique partagé par Godot et mobile (futur), routes REST classiques. Pas de serveur dupliqué.

Sécurité validée : **liste blanche et confirmation pour toute action système à risque** — pas un bridage par défaut de tout le reste. Luca's a un accès large et réel à ce dont elle a besoin pour être utile ; c'est au moment du doute ou du risque qu'elle demande, et Cyril tranche. Jamais de script généré dynamiquement par le LLM, jamais d'exécution de code auto-généré hors sandbox. Formulation de référence : `VISION_LONG_TERME.md` §4 — en cas d'écart entre les deux fichiers, c'est la vision qui fait foi.

**État de `security/` au 01/08/2026 — niveau 0, observation seule.** Guardian, Privacy Shield et Ransomware Watch existent en ébauche testée (62 tests) : ils détectent et rapportent, ils n'agissent jamais. Aucun process tué, aucune connexion coupée, aucun fichier restauré, aucun appel à un service externe. Leur donner un pouvoir d'action défensif est une décision distincte, à valider par Cyril.

La détection de rançongiciel repose sur les **métadonnées seules** (extensions connues, notes de rançon, rafale de modifications) et sur des **fichiers-appâts** déployés explicitement. Elle ne lit jamais le contenu des documents : l'analyse d'entropie serait plus fiable mais obligerait le capteur à ouvrir les fichiers personnels — décision qui revient à Cyril.

**Surveillance continue branchée sur le daemon** (01/08/2026) : `SecurityMonitor` orchestre les trois capteurs depuis `orion_daemon.py` — process et réseau toutes les 5 minutes, fichiers toutes les 15. Les signaux ne sont rapportés qu'une fois : un état persistant (`data/security_state.json`) déduplique d'un balayage à l'autre et d'un redémarrage à l'autre, et oublie un signal après 3 jours d'absence pour que son retour soit de nouveau une information. Les alertes atterrissent dans `system_events`, donc dans le contexte que Luca's injecte au LLM.

**Niveau 1 livré le 01/08/2026 — les capteurs ont une mémoire.** `security/history.py` retient ce que la machine a l'habitude de faire, et deux capteurs s'en servent :

- **Premier contact externe** : un programme qui contacte une adresse publique pour la première fois est signalé. La clé retenue est (programme, IP) sans le port — les ports source changent à chaque connexion, les inclure ferait tout paraître nouveau.
- **Persistance au démarrage** (`security/persistence_watch.py`) : lecture des clés `Run`/`RunOnce` du registre et du dossier Démarrage. CRITIQUE si l'entrée pointe vers un répertoire temporaire, WARNING si elle est apparue depuis le dernier balayage. Le module lit le registre, il n'y écrit jamais.

**Période d'apprentissage de 24 h** (`SECURITY_LEARNING_HOURS`) : les capteurs observent sans alerter au démarrage. Mesuré sur cette machine, sans elle : **27 alertes au premier balayage** — chaque navigateur et application contactant Internet. Le rapport aurait été illisible et abandonné.

⚠️ **Sur les hooks clavier** : `ROADMAP` annonçait « suivi des hooks clavier (keylogger) ». Ce n'est **pas observable depuis Python de façon portable** — énumérer les hooks `SetWindowsHookEx` demande des appels natifs Win32 que `psutil` n'expose pas. Un module nommé « détecteur de keylogger » qui ne détecte rien donnerait une fausse assurance, exactement ce que §4.1 cherche à éviter. La détection de persistance vise le même adversaire par un angle réellement observable : un keylogger doit survivre au redémarrage.

**Niveau 1 clos le 01/08/2026.** Cinq capteurs (`guardian`, `privacy_shield`, `ransomware_watch`, `persistence_watch`, `monitor`), une mémoire partagée (`history`), 94 tests. Les chemins d'état sont ancrés sur la racine du projet — le daemon étant prévu en service Windows via NSSM, un chemin relatif faisait repartir l'apprentissage de zéro à chaque lancement.

**Les deux paliers suivants demandent une décision de Cyril, pas du code :**
- **Analyse d'entropie** des fichiers pour la détection de chiffrement : plus fiable que les métadonnées, mais le capteur ouvrirait les documents personnels.
- **Détection native des hooks clavier** : impose une dépendance Win32, `psutil` ne les expose pas.

Tant que ces deux points ne sont pas tranchés, `security/` reste au niveau 1 — ce qui suffit au principe §4.1 pour les extensions d'autonomie envisagées à court terme, mais pas pour un pouvoir d'action défensif.

**Nouveau principe acté le 01/08/2026 — la liberté est conditionnée à la protection.** Guardian et Privacy Shield (`security/`) deviennent une dépendance directe de toute extension future des libertés d'action de Luca's : plus ils sont matures et testés, plus le périmètre d'autonomie peut s'élargir. Concrètement pour le séquencement de ce fichier, aucune phase n'ouvre de nouveaux droits d'action (OS Controller, automation, exécution autonome) tant que ces deux modules ne sont pas au moins ébauchés et testés. Ils n'appartiennent donc plus au « polish » de la Phase 5 — ce sont des prérequis. Doctrine : `VISION_LONG_TERME.md` §4.1, résumé opposable : `CLAUDE.md`.

---

## 5. Points de vigilance infra (leçons du 30/07/2026)

- **Ollama en double instance** : l'appli tray Ollama relance automatiquement un serveur si on tue le process en CLI. Résultat : deux instances sur le port 11434, chacune avec un jeu de modèles différent, causant des 404 "model not found" alors que le modèle existe bel et bien. **Solution appliquée** : tuer `ollama.exe` ET `ollama app.exe`, puis relancer uniquement via `ollama serve` en CLI. **À faire avant de clore Phase 2** : vérifier dans les paramètres Ollama si le démarrage automatique avec Windows est activé, et le désactiver si besoin pour éviter que le problème revienne à chaque redémarrage du PC.
- **SQLite et threads FastAPI** : `OrionCore()` est recréé à chaque requête `/chat` plutôt que partagé en singleton, pour éviter les erreurs de thread SQLite. Fonctionne car tout l'état vit dans le fichier `.db`, pas en mémoire Python. À garder en tête si on introduit du code qui suppose un état Python persistant entre requêtes.
- **Toujours vérifier l'existence d'un backup avant suppression** : lors du nettoyage Phase 0, les vrais dossiers `core/` et `ui/` ont été supprimés par erreur (confusion avec les fantômes `Fichier core/`/`Fichier ui/`, noms très proches). Récupérés via un zip de backup antérieur (`OrionProject/OrionAI.zip` du 26/07). Réflexe à garder : zipper le dossier projet avant tout nettoyage manuel.
- **Les fixtures vides valident des comportements qui cassent sur des données réelles** (leçon du 01/08/2026, quatre correctifs successifs annoncés « fonctionnels » sur une application cassée). `_FakeMemory.load_history()` rendait `[]` en dur : tous les tests vision tournaient donc sur une conversation neuve, où le bloc d'observation se retrouvait **mécaniquement** collé à la question. En usage réel, avec 100 messages d'historique, il arrivait en 4ᵉ position sur 91 et se faisait noyer — le modèle répondait à une vieille question. Le protocole de test était faux, pas le code testé.
  **Règle** : pour toute fonction qui dépend du **volume** ou de la **position** des données, au moins un test doit tourner sur un état **chargé** — historique long, base non vide, cache peuplé. Un test sur état vide ne prouve rien sur ces deux propriétés. Et vérifier qu'un nouveau test **tombe bien sur l'ancien code** avant de le déclarer probant (ici : `assert 92 < 2`).
  Les angles morts de la même famille, à surveiller : base neuve, cache froid, liste à un seul élément, premier lancement.

### Leçons du chantier RAG & Vision (01/08/2026)

- **Ne jamais indexer un dossier sans regarder ce qu'il contient.** L'indexation de `C:/Users/PC/Documents` a fait entrer en base « Mots de passe Microsoft Edge.csv » et « proton-recovery-kit.pdf ». Des identifiants en clair dans une base vectorielle deviennent **récupérables par une simple question**, et le LLM les recopie dans sa réponse puisqu'on les lui fournit comme contexte. J'avais vérifié le *volume* (46 fichiers, « raisonnable »), pas la *nature*. `SECRET_PATTERNS` refuse désormais ces fichiers **sans même les ouvrir** — mais la liste a raté un cas le jour même où elle a été écrite (« Bitdefender SecurePass **Recovery Key**.pdf », alors qu'elle contenait « recovery-kit »). **C'est un filet, pas une garantie : la vraie protection est de ne pas ranger ses secrets dans un dossier indexé.**
- **Un seul fichier peut écraser toute la base.** `log.txt` (0,7 Mo) produisait 818 morceaux sur 1083 — 76 % du total — et rendait 35 vrais documents introuvables. ⚠️ **Retirer `.log` des extensions acceptées n'aurait rien changé : le fichier s'appelait `log.txt`.** D'où deux tests, sur l'extension *et* sur le radical du nom. Un document légitimement volumineux est signalé, pas retiré d'office.
- **La recherche vectorielle ne sait pas comparer des dates.** « salaire de juillet 2025 » remontait les bulletins de février, avril et janvier 2026 : pour un modèle d'embeddings, deux dates de bulletin de paie sont sémantiquement voisines, et le mois demandé est exactement l'information qu'il écrase. `core/dates.py` extrait les périodes des deux côtés et filtre. **Quand une période est nommée, on interroge toute la base avant de filtrer** — un élargissement ×10 ne suffisait pas.
- **Le silence fait fabriquer le modèle.** Quand aucun document ne couvre la période, ne rien injecter a conduit Luca's à **inventer un nom de fichier et un montant**, en imitant le format des réponses correctes qui précédaient. Une réponse inventée est indiscernable d'une vraie. La recherche infructueuse est désormais annoncée, **en nommant la période manquante** — un refus générique ne suffisait pas.
- **Une question elliptique hérite du verdict de la précédente.** « Et pour 2024 ? » n'a pas de sujet propre : reclassée dans le vide, elle donnait `AUCUN` une fois sur deux, et le verdict basculait sur un mot de la *réponse* précédente. Deux pistes fermées par la mesure, **à ne pas rouvrir** : doubler le contexte ne change rien, et retirer la réponse précédente est pire (4/7 contre 5/7).
- **Deux mécanismes reposent sur la grammaire, pas sur du vocabulaire** — la garde déictique (`ce`, `cette`, `ces` désignent l'écran) et l'héritage elliptique. C'est ce qui les distingue d'un mot-clé de plus : ils valent pour des formulations que personne n'a besoin d'énumérer. Quand le prompt engineering est épuisé — vérifié sur trois modèles pour la déixis, et une consigne « suite de conversation » dégrade de 4/5 à 2/5 — c'est la piste à prendre.
- **Ses propres essais polluent la mémoire, et le résultat suivant en dépend.** Plusieurs fois pendant ce chantier, j'ai cru mesurer un bug alors que je mesurais l'écho de mon essai précédent : les six derniers messages contenaient exactement le motif d'échec, réinjecté par `SOURCE_HISTORY_MESSAGES`. **Purger la base entre deux validations en conditions réelles**, sinon la mesure ne veut rien dire.

---

## 5.1 Décisions de sécurité — tranchées le 01/08/2026

Trois surfaces de sortie n'avaient aucun garde-fou, contrairement au LLM cloud et au TTS. Cyril a arbitré les trois.

**API sur `127.0.0.1` — fait.** L'API n'a aucune authentification et `GET /history` renvoie l'intégralité des conversations : l'exposer au réseau la rendrait lisible par tout appareil du WiFi. Elle n'écoute donc plus que sur ce PC (`API_HOST` dans `config.py`). Pas de jeton pour l'instant, le mobile n'étant pas branché.
**➜ À revoir en Phase 5** : le passage à `0.0.0.0` pour la PWA exigera un jeton partagé *au préalable*, pas après.

**`cmd` retiré de la liste blanche — fait.** Un interpréteur de commandes permet de lancer n'importe quel programme : le laisser dans une liste blanche revient à n'en avoir aucune. `SHELL_LIKE_APPS` et la journalisation distincte (`automation_shell_opened`) restent en place pour le jour où un shell reviendrait derrière une confirmation explicite, quand le moteur de décision existera.

**Filtre de recherche web — fait.** `modules/web_search.py` refuse, avant tout appel réseau, les requêtes contenant une donnée réellement identifiante : IBAN, numéro de carte ou de compte (motifs numériques), et expressions comme « mon solde » ou « mon numéro de carte ». Volontairement **plus étroit** que `KEYWORDS_SENSITIVE` : « crédit », « banque », « budget », « risque » et « portfolio » restent cherchables, car un filtre qui empêche l'usage normal finit désactivé, donc inutile.

## 6. Renommage Luca's — partie visible faite le 01/08/2026

**Fait** : tout ce que Cyril voit affiche désormais « Luca's » — `SYSTEM_PROMPT`
et `WINDOW_TITLE` dans `config.py`, titre de fenêtre, libellé de l'interlocuteur
dans le chat, placeholder de saisie, infobulles TTS, message « réfléchit… »,
titres et prose de `CLAUDE.md` et `README_INSTALL.md`.

**Volontairement inchangé** : tous les noms techniques — `OrionCore`,
`core/orion_core.py`, `orion_daemon.py`, `Orion3D/`, `memory/orion_memory.db`,
le chemin `C:\OrionAI`, l'organisation GitHub `OrionProject76`. Les renommer
casserait imports et chemins pour un gain nul.

**Leçon de cette session** : une première tentative par expression régulière
sur `\borion\b` a transformé `self.orion` en `self.luca's` — erreur de syntaxe
immédiate. Un renommage se fait par remplacements exacts, chaîne par chaîne,
jamais par motif générique sur du code.

### Ce qui reste (ancien contenu de cette section)

Renommage acté par Cyril le 29-30/07/2026. À faire une fois S2 stabilisé :
- Titre fenêtre PySide6, prompts système du LLM, messages TTS
- Éventuellement le nom du dossier projet (`C:\OrionAI` → autre chose) — optionnel
- Mise à jour de `CLAUDE.md`, `ROADMAP.md`, `IDEAS.md` (remplacement des mentions "Orion"/"OrionAI")

Ne pas faire ce renommage avant S2 pour éviter de casser des chemins/imports en plein travail sur la mémoire enrichie.

---

## 7. Règles de mise à jour de ce fichier

- Après chaque brique validée : déplacer l'élément vers "État actuel ✅", repréciser la nouvelle étape immédiate.
- Ne jamais sauter une phase pour une fonctionnalité "fun" tant que le socle n'est pas stable.
- Toute nouvelle idée émergente va dans `IDEAS.md`, pas ici.
