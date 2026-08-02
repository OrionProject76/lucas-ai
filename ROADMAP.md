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
Reclassé en Phase 4 (S5-S6, voir tableau §3 — « Phase 6 » utilisé ici avant
le 02/08/2026 était une erreur de numérotation, corrigée lors de l'audit de
fiabilité : le tableau §3 ne définit que les Phases 0 à 5), branche
`experimental/godot-avatar`. Ne bloque pas la release.

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

**Fait le 02/08/2026** : les PDF scannés (cartes d'identité, certains
contrats) passent maintenant par `modules/ocr_engine.py` (RapidOCR, déjà
utilisé pour l'écran) quand pypdf n'extrait aucune couche texte. PyMuPDF
rend chaque page en image temporaire — supprimée dans tous les cas, ce
sont potentiellement des pièces d'identité — puis l'OCR lit le texte,
page par page. Si l'OCR est indisponible (dépendance absente) ou ne
trouve rien d'exploitable, le document est signalé avec un motif
explicite, comme avant — jamais indexé à moitié en silence. Voir
`memory/index_documents.py` (`_read_pdf`, `_ocr_pdf`, `_rasteriser_pdf`)
et `test_index_documents.py`.

**Prérequis avant de commencer S2 :** vérifier qu'Ollama tourne sans doublon de process (voir section 5 — point de vigilance infra).

---

## 3. Jalons futurs

| Phase | Semaine | Focus | Statut |
|---|---|---|---|
| **Phase 0 — Audit** | S0 | Nettoyage, inventaire | ✅ Fait (avec incident de suppression accidentelle résolu — voir CLAUDE.md) |
| **Phase 1 — Cerveau solide** | S1 | FastAPI unique + World Model | ✅ **Fait et validé aujourd'hui** |
| **Phase 2 — Mémoire & Finance** | S2 | RAG, TTS, Finance CSV | ✅ Fait le 01/08 — reste la validation TTS à l'oreille dans l'UI |
| **Phase 3 — Vision & Voix** | S3-S4 | VLM écran, Avatar QPainter V3, 5 modes de présence | 🟡 En cours — VLM écran ✅, 5 modes de présence ✅ |
| **Phase 4 — Expansion** | S5-S6 | PWA mobile, sync, Godot 4 V1 (branche expérimentale) | 🟡 Amorcé — côté serveur du pont audio branché (02/08), PWA/auth/tunnel restent à faire |
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

Le moteur STT (`modules/stt_engine.py`) est **déjà écrit et testé**, commité le 01/08 comme socle. **Branché côté serveur le 02/08/2026** (voir la section dédiée plus bas) — mais toujours sans client réel pour l'alimenter. **Il ne compte donc toujours pas comme une avancée de Phase 3** ni de Phase 4 pleinement livrée : seule la moitié serveur existe.

> **Note de numérotation — partiellement harmonisée le 02/08/2026.** Ce tableau place le pont mobile en **Phase 4** (semaines S5-S6). Les mentions « Phase 5 » dans `config.py`, `README_INSTALL.md` et `stt_engine.py` (écrites le 01/08, reprenant le libellé de semaine) ont été corrigées en « Phase 4 » pour suivre ce tableau. **Reste non résolu** : la section « Priorités de Développement » de `CLAUDE.md` situe elle le « Mobile Bridge » en **S7**, pas S5-S6 — un désaccord de SÉQUENÇAGE, pas seulement de vocabulaire, qui demande une vraie décision (quand le pont mobile passe-t-il réellement, avant ou après OS Controller/Automation ?) et pas juste un remplacement de texte. Toujours à trancher lors d'une passe dédiée.

### 🟢 Session du 02/08/2026 — premier appelant réel de la STT, côté serveur uniquement

À la demande de Cyril de creuser la suite du pont mobile. Aucun matériel S25
Ultra n'est disponible pour tester avec un vrai client : ce qui suit est donc
strictement le **côté PC** du pont — la moitié qui peut être construite et
vérifiée sans téléphone.

**Fait** :
- `api/server.py` gère maintenant un troisième type de message WebSocket,
  `"audio"` (en plus de `"hello"` et `"chat"`) : `audio_base64` →
  `STTEngine.transcribe_base64()` → le texte transcrit suit **exactement**
  le même chemin qu'un message tapé (décision vision, `LucasCore.ask()`,
  réponse). C'est le premier appelant réel de `modules/stt_engine.py`
  depuis son écriture le 01/08.
- `STATE_LISTENING` — un des 5 modes de présence, présent dans le
  protocole depuis le début mais jamais émis faute de micro — s'émet
  maintenant réellement pendant la transcription.
- **Bug trouvé en testant de bout en bout avec un vrai fichier audio (pas
  seulement des mocks)** : `_FasterWhisperBackend` utilisait
  `device="auto"`, qui tente CUDA sur cette machine et échoue (« Library
  cublas64_12.dll is not found »). Le commentaire du module dit depuis le
  01/08 que faster-whisper est choisi pour tourner en CPU, justement pour
  ne pas se disputer la VRAM avec Ollama (`VISION_LONG_TERME.md` §3) —
  `"auto"` contredisait cette intention documentée, indépendamment du
  plantage. Corrigé en `device="cpu"` explicite.
- `faster-whisper` installé (`requirements.txt`) et vérifié réellement
  disponible (`STTEngine().is_available()` → `True`).
- Validé à trois niveaux : 6 tests avec un moteur STT doublé
  (`test_server.py`), puis un vrai fichier WAV (silence quasi pur, généré
  par script) envoyé à l'API réellement lancée — cycle
  `listening → idle` confirmé sans erreur après la correction CPU, en
  passant par le vrai modèle Whisper.

**Pas fait, et pas décidé seul** — trois points distincts, pas un seul :

1. **Aucun client mobile n'existe.** Ni PWA, ni manifest, ni service
   worker, ni page HTML — le dossier `static/` n'existe pas. C'est un
   chantier à part entière (choix de stack pour la PWA, design de
   l'interface tactile), pas une extension de ce qui vient d'être fait.
2. **L'API n'a toujours aucune authentification**, et écoute toujours sur
   `127.0.0.1` uniquement — donc inatteignable depuis un téléphone en
   l'état. Le jeton partagé documenté comme prérequis (§5.1, « À revoir en
   Phase 4 ») n'est pas construit. Passer à `0.0.0.0` sans ce jeton
   d'abord exposerait `GET /history` (tout l'historique de conversation)
   à n'importe quel appareil du réseau — relève du cas 1 de l'Autonomie
   d'exécution (`CLAUDE.md`) : accès réseau externe, à ne jamais faire
   sans validation explicite.
3. **Le protocole de tunnel (Tailscale vs WireGuard) n'est pas choisi** —
   `VISION_LONG_TERME.md` §2 Pilier 3 le laisse explicitement ouvert
   (« à définir en Phase Mobile »). C'est un choix d'architecture qui
   engage la suite (cas 3 de l'Autonomie d'exécution), pas un détail
   d'implémentation à trancher en passant.

**Proposition pour la suite, validée par Cyril → faite dans la foulée** :
le jeton d'authentification (point 2) est construit, `API_HOST` reste
`127.0.0.1` par défaut — c'est un prérequis sans risque réseau tant que le
bind n'a pas changé.

**Fait** : `config.API_TOKEN` (vide par défaut, `.env` — `API_TOKEN=`).
Un jeton vide désactive toute vérification, comportement identique à avant
ce mécanisme — vérifié par des tests dédiés ET en conditions réelles
(API relancée, `POST /chat` sans aucun jeton, toujours `200`). `/chat`,
`/history`, `/system` exigent `Authorization: Bearer <jeton>` dès qu'une
valeur est renseignée ; `/status` reste toujours ouvert (rien de sensible).
Le WebSocket `/ws` vérifie un paramètre de requête (`?token=...`, pas un
en-tête — un client WebSocket de navigateur ne peut pas en poser) **avant**
`accept()`, et ferme au niveau protocole (code 1008) si absent/invalide,
sans jamais ouvrir la connexion. Comparaison en temps constant
(`secrets.compare_digest`) pour ne pas fuir la longueur/le préfixe du
jeton par le temps de réponse.

**Reste pour Cyril seul** : renseigner une vraie valeur dans `.env` et
passer `API_HOST` à `0.0.0.0` — deux actions liées, jamais l'une sans
l'autre — puis les points 1 (PWA) et 3 (tunnel) ci-dessus.

### 🟢 Session du 02/08/2026 (suite) — scaffold PWA : chat + micro + caméra + avatar léger

Point 1 ci-dessus (PWA) fait, en vanilla JS/HTML/CSS sans build step —
choix validé par Cyril, cohérent avec l'absence de toute chaîne d'outils
JS dans le reste du projet.

**Fait** :
- `static/` : `manifest.json`, `sw.js` (cache l'app shell uniquement,
  jamais `/ws` ni un futur appel REST), `index.html`, `css/style.css`,
  `js/{avatar,websocket,chat,audio,camera,app}.js`, icônes PNG générées
  par script (PIL).
- Monté à `/app` dans `api/server.py` (`StaticFiles`, en dernier pour ne
  jamais capter les routes JSON existantes) — testé.
- **Avatar** : palette et logique reprises EXACTEMENT de
  `ui/avatar_widget.py` (PySide6), pas réinventées — mêmes dégradés par
  état, même ambre pour WATCHING (choix de sécurité, témoin de capture),
  même témoin clignotant en renfort. Les trois clients (PySide6, Godot,
  PWA) doivent se ressembler pour la même Luca's.
- **Micro** : bouton → `MediaRecorder` → base64 → message `"audio"`
  existant (aucun second pipeline STT, voir la session précédente).
- **Caméra** — ajoutée en cours de scaffold, à la demande de Cyril : bouton
  → `getUserMedia({video})` → une frame capturée sur `<canvas>` → base64
  → nouveau message WebSocket `"image"`. Réutilise le pipeline vision
  EXISTANT plutôt qu'un système séparé :
  - `core/lucas_core.py` : `_describe_screen()` découpé en capture +
    `_describe_image_at()` (coeur OCR/VLM partagé). Nouvelle
    `_describe_camera_image(image_path, user_message)` appelle ce même
    coeur sans capturer l'écran. `ask()`/`_build_messages()` acceptent
    un `image_path` optionnel qui FORCE la vision (le bouton caméra est
    le signal, pas besoin de `should_use_vision()`), et reste sous la
    même garde `not is_cloud` que l'écran.
  - `api/server.py` : message `"image"` → décodage base64 vers fichier
    temporaire (même logique que `STTEngine.transcribe_base64`) →
    **réutilise l'état WATCHING** existant (validé par Cyril : même
    témoin que la capture d'écran, "Luca's regarde quelque chose") →
    `lucas.ask(message, image_path=...)` → fichier temporaire supprimé
    dans tous les cas.
  - **VLM reste désactivé** (`VLM_ENABLED = False`, décision v1.0
    inchangée) — validé explicitement par Cyril. Conséquence connue :
    une photo sans texte (objet, visage, paysage) ne produit aucun
    contexte visuel pour l'instant, seul l'OCR fonctionne. Limitation
    documentée, pas un bug.
- **Tests** : 6 nouveaux dans `test_server.py` (message `"image"` :
  cycle watching→speaking→idle, légende par défaut/fournie, fichier
  temporaire présent pendant l'appel puis supprimé, image absente/base64
  invalide gérées sans planter), 5 nouveaux dans `test_vision_routing.py`
  (photo force la vision sans le classifieur, ne recapture pas l'écran,
  le chemin donné atteint bien l'OCR et le VLM, jamais vers le cloud,
  dégrade silencieusement si rien n'est exploitable), 3 pour le montage
  statique. 605 tests, tous verts.
- **Validation en conditions réelles** (pas seulement les tests) : API
  relancée avec le code du jour, PWA ouverte dans un vrai navigateur
  (Chrome via l'extension) — cycle de chat complet vérifié de bout en
  bout jusqu'à Ollama (pas un mock), bulles stylées correctement, avatar
  revenu à `idle`. Bouton micro testé réellement : `NotFoundError`
  (aucun micro sur ce PC — cohérent avec toute la prémisse du projet),
  message d'erreur affiché proprement, pas de plantage. Bouton caméra :
  confirmé en attente du dialogue de permission natif du navigateur
  (`navigator.permissions.query` → `"prompt"`) — chemin non poussé plus
  loin (dialogue natif, pas interactif depuis l'automatisation), mais le
  code de gestion d'erreur est identique à celui du micro, déjà validé.

**Pas fait, pas changé** : `API_HOST` reste `127.0.0.1` (la PWA n'est
donc testable que sur cette machine pour l'instant, pas depuis un vrai
téléphone) ; aucun test avec un vrai micro/caméra téléphone puisqu'aucun
n'est branché ; format audio du navigateur (`audio/webm;codecs=opus`) non
vérifié contre le vrai backend Whisper — seul un WAV synthétique l'a été
jusqu'ici (session précédente).

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

## 5.2 Audit de fiabilité effectué le 02/08/2026 — résultat : propre après corrections

Fait à la demande de Cyril, avant de lancer le renommage technique complet
(§6) : « partir d'une base saine avant de toucher à plein de fichiers ».
Cinq vérifications, plus une trouvée en cours de route.

**1. Chaque fichier Python commité s'importe sans erreur — 1 échec trouvé et corrigé.**
Testé sur un `git worktree` détaché sur HEAD (pas la copie de travail) : les
74 modules `.py` du dépôt ont été importés un par un. `modules/weather_manager.py`
échouait — un bloc de test en bas de fichier, **sans garde `if __name__`**,
appelait `requests.get()` vers wttr.in dès l'import, donc plantait sans accès
réseau. Corrigé : bloc de test déplacé sous la garde, et l'exception
`ValueError("Ville invalide")` (qui n'était pas rattrapée par le `except`
sur `RequestException`) est maintenant traitée comme les autres échecs.
Module toujours non branché ailleurs dans le code — voir la note § 1 « statut
réel à clarifier », qui reste largement d'actualité : la correction rend le
module *important sans crasher*, pas *fonctionnel contre le vrai wttr.in*
(l'URL utilisée, `?format=3`, ne correspond probablement pas au format à 4
lignes que le code suppose — non vérifié contre le service réel, à faire
séparément si ce module est un jour branché).

**2. Suite de tests complète sur l'état réellement commité — propre.**
Même worktree détaché : 554/554 tests passaient déjà avant les corrections
de cet audit (575/575 après, avec les 21 nouveaux tests des points 1 et
« trouvaille additionnelle » ci-dessous).

**3. Aucun fichier fantôme ou doublon réintroduit — propre.**
Recherche sur `git ls-files` : aucun nom avec espace inhabituel, aucun motif
« Fichier », « copy », « backup », « (1) », « _old ». Les modules qui se
ressemblent par paire (`stt_engine.py`/`stt_manager.py`,
`finance_categorizer.py`/`finance_manager.py`) sont bien tous les deux
utilisés (imports confirmés depuis `core/orion_core.py`, `ui/`, et leurs
tests respectifs) — pas des doublons.

**4. Cohérence entre CLAUDE.md, ROADMAP.md, VISION_LONG_TERME.md, IDEAS.md — 4 écarts trouvés et corrigés.**
Lecture croisée complète des quatre fichiers. Un écart significatif, trois
mineurs :
- **Règle 11 jamais réconciliée avec le TTS hybride** — « Piper/Kokoro seuls »
  contredisait la section TTS (01/08/2026) qui fait d'edge_tts le moteur par
  défaut. Même oubli que ce qui avait été corrigé pour les règles 3 et 12,
  mais jamais fait pour la 11. Corrigé : nouvelle précision dans CLAUDE.md,
  même format que les règles 3/12.
- **« Phase 6 » utilisé sans être défini** — le tableau des phases (§3) ne va
  que jusqu'à la Phase 5, mais ROADMAP.md §1 et VISION_LONG_TERME.md
  parlaient tous deux de « Phase 6 » pour Godot / l'avatar final. Corrigé
  dans les deux fichiers (Godot reclassé en Phase 4, qui est là où il vit
  déjà dans le tableau §3 ; VISION_LONG_TERME.md renvoie maintenant à
  « au-delà de la Phase 5 »).
- **CLAUDE.md listait audio/webcam en S1** alors que ROADMAP.md documente
  depuis le 01/08 que ces deux capteurs sont bloqués jusqu'au pont mobile
  (le PC n'a ni micro ni caméra). ROADMAP citait déjà CLAUDE.md comme source
  de l'écart sans le corriger — fait maintenant.
- **IDEAS.md pointait vers un renommage « à faire »** dans une section de
  ROADMAP.md qui documente désormais un renommage largement fait. Le titre
  dit directement « Barre Luca's » maintenant, sans renvoi qui deviendrait
  lui-même obsolète après le chantier de renommage technique.

**5. Rien de sensible dans l'historique commité — propre.**
`git log --all` sur les noms de fichiers : aucun fichier n'a jamais été
ajouté sous `data/documents/`, `*.db`, ou un nom évoquant un secret.
`git log -p --all` sur le contenu : aucune clé API non vide n'a jamais été
commitée (`OPENAI_API_KEY` reste vide dans `.env.example` à travers toute
l'histoire) ; les seules chaînes ressemblant à des IBAN sont des données de
test explicites (`test_index_documents.py`, `test_router.py` — le format
placeholder « FR76 3000... » sert à vérifier que ces données ne sortent
JAMAIS, pas de vraies coordonnées bancaires de Cyril). `.env` réel n'a
jamais été commité.

**Trouvaille additionnelle, hors des 5 points demandés — corrigée, jugée
suffisamment grave pour ne pas attendre :** `modules/calculator.py`
appelait `eval(expression)` directement, avec un commentaire affirmant à
tort « évaluation sécurisée ». `eval()` exécute n'importe quel code Python,
pas seulement des maths — un vecteur d'exécution de code arbitraire si ce
module était un jour exposé comme outil appelable par le LLM (ce que son nom
et son intention suggèrent). Non branché ailleurs dans le code au moment de
la correction. Remplacé par un évaluateur limité à un sous-ensemble d'AST
(nombres et opérateurs arithmétiques de base, rien d'autre) —
`test_calculator.py` vérifie explicitement que les expressions comme
`__import__('os').system(...)` sont refusées, pas exécutées.

**Modules restés sans test après cet audit** (hors périmètre — non touchés
car ni cassés ni concernés par les 5 points) : voir §1 « statut réel à
clarifier » pour le reste de la liste (`rag_manager.py`, `vision_manager.py`,
`automation_manager.py`, `web_search.py` ont en réalité des tests, cette
note datait d'avant leur écriture — seuls `weather_manager.py` et
`calculator.py` étaient réellement orphelins, tous deux couverts
maintenant).

## 5.3 Vérification indexation RAG + recalibrage — 02/08/2026

À la demande de Cyril de confirmer que `data/documents/` est bien indexé et
le seuil recalibré.

**Indexation confirmée** : les deux fichiers présents dans `data/documents/`
(`ANTS - Demande de changement d'adresse - Récapitulatif.pdf`,
`Document.docx`) sont bien indexés, avec du contenu réel vérifié
directement dans la collection ChromaDB (4 morceaux pour l'un, 3 pour
l'autre, texte cohérent avec le PDF/docx source).

**⚠️ Découverte importante, à connaître avant de relancer une indexation** :
la collection contient en réalité **39 documents, 229 morceaux** — pas
seulement les 2 fichiers de `data/documents/`. Les 37 autres (bulletins de
paie, déclaration de revenus, CV, offres d'emploi, attestations…)
correspondent à la calibration documentée dans `config.py` du 01/08/2026,
faite sur **`C:/Users/PC/Documents`** — le vrai dossier Documents de
Cyril, pas le dossier `data/documents/` du dépôt (`DOCUMENTS_DIR` dans
`config.py`).

**Conséquence concrète, pour éviter un accident** : `index_directory()`
retire de la base tout document qu'il ne retrouve pas dans le dossier
scanné (nettoyage des orphelins, voir `memory/index_documents.py`). Lancer
`python -m memory.index_documents` **sans argument** scanne
`data/documents/` par défaut — seulement 2 fichiers — ce qui **supprimerait
les 37 autres documents indexés depuis `C:/Users/PC/Documents`**, un vrai
dossier personnel, pas un dossier de test. Cette vérification a donc été
faite en lecture seule (`RAGManager().indexed_documents()`,
`collection.get()`) — **`index_directory()` n'a jamais été appelé**,
justement pour ne pas risquer ce nettoyage. Si une réindexation est un
jour nécessaire, elle doit rescanner `C:/Users/PC/Documents` explicitement,
jamais le dossier par défaut du dépôt.

**Seuil recalibré** : `demos/calibrate_rag.py` relancé en conditions
réelles sur la collection actuelle. Toujours 39 documents, mais 229
morceaux au lieu des 275 documentés le 01/08 — au moins un document a changé
depuis (lequel n'est pas identifié). La valeur codée (`0,33`) n'avait de
toute façon jamais suivi la recommandation du premier calibrage (`0,34` —
écart d'un centième entre le commentaire de `config.py` et la constante,
présent depuis le 01/08). Les deux calibrages, à un mois d'écart et sur une
collection qui a changé, retombent sur la même valeur : `RAG_MAX_DISTANCE`
corrigé à `0,34` (garde 90 % des extraits utiles, bloque 100 % des
questions hors sujet — contre ~85-88 % à `0,33`). 590/590 tests après le
changement.

## 6. Renommage Luca's — partie visible faite le 01/08/2026, technique fait le 02/08/2026

**Fait le 01/08/2026** : tout ce que Cyril voit affiche désormais « Luca's » —
`SYSTEM_PROMPT` et `WINDOW_TITLE` dans `config.py`, titre de fenêtre, libellé
de l'interlocuteur dans le chat, placeholder de saisie, infobulles TTS,
message « réfléchit… », titres et prose de `CLAUDE.md` et `README_INSTALL.md`.

### Renommage technique — fait le 02/08/2026, après l'audit de fiabilité (§5.2)

Exécuté à la demande explicite de Cyril, avec la même rigueur que d'habitude :

- **Sauvegarde avant de toucher aux chemins** : archive complète du dépôt
  (hors `venv/` et `.git/`) sur le Bureau, avant le premier `git mv`.
- **Remplacements par identifiants exacts**, jamais un motif générique sur
  "orion" seul (voir la leçon ci-dessous) — chaque token composé
  (`OrionCore`, `orion_core`, `Orion3D`, etc.) remplacé séparément, puis les
  mots isolés `orion`/`Orion` restants, uniquement dans les fichiers de
  code (jamais dans les `.md`, pour préserver la narration historique).
- **Imports vérifiés** : les 74 modules `.py` du dépôt importés un par un
  après renommage — 0 échec.
- **Suite de tests complète** : 575/575 (554 + les tests ajoutés lors de
  l'audit §5.2), rejouée deux fois pour écarter un test à particules
  (`test_avatar.py`) intermittent mais confirmé sans lien avec le
  renommage (passe de façon fiable isolément).
- **Démarrage réel vérifié**, pas seulement les tests : l'API relancée
  avec le code renommé (`uvicorn api.server:app`), `GET /status` et
  `GET /system` répondent, et un vrai `POST /chat` est passé de bout en
  bout par `LucasCore.ask()` jusqu'à Ollama et retour — pas un mock.

**Renommé** :
- `OrionCore` → `LucasCore` ; `core/orion_core.py` → `core/lucas_core.py`
- `OrionDaemon` → `LucasDaemon` ; `orion_daemon.py` → `lucas_daemon.py`
- `Orion3D/` → `Lucas3D/` (dossier Godot, via `git mv` — historique préservé)
- `memory/orion_memory.db` → `memory/lucas_memory.db` (fichier de données,
  non suivi par git — renommé sur le disque, contenu intact)
- `data/orion_daemon.db` → `data/lucas_daemon.db` (idem)
- Le champ de protocole WebSocket `from_orion` → `from_lucas`, sur les DEUX
  faces du contrat (`api/protocol.py` et `Lucas3D/scripts/websocket_client.gd`)
  en même temps — c'était le seul renommage risqué côté GDScript, câblé
  correctement dès le départ plutôt qu'en deux temps
- Les signaux/variables Godot `Global.orion_state`, `orion_speaking`,
  `orion_idle`, `orion_state_changed` → équivalents `lucas_*`
- Quelques identifiants UI mineurs : `add_orion_button`, `play_orion_audio`
  (`ui/chat_widget.py`), `last_orion_response` (`ui/main_window.py`)
- Les binaires Godot exportés (stables, non suivis) et les entrées
  `.gitignore` correspondantes

**Délibérément NON renommé** (décisions distinctes, documentées, pas des
oublis) :
- **Le chemin `C:\OrionAI`** — risque opérationnel direct : Claude Code
  travaille dans ce dossier en continu au moment du renommage ; le renommer
  sous ses propres pieds risquait de casser l'accès aux outils en plein
  chantier, sans aucun moyen de le signaler si ça avait mal tourné. À faire
  séparément, avec Cyril informé du risque avant de lancer.
- **L'organisation GitHub `OrionProject76`** — identité externe partagée,
  casse tous les liens/clones existants ; décision à trancher explicitement,
  pas à exécuter en trouvant l'occasion.
- **La collection ChromaDB `"orion_docs"`** (`modules/rag_manager.py`) —
  nom de stockage interne persisté sur le disque de Cyril ; le renommer
  orphelinerait ses documents déjà indexés pour un gain purement cosmétique,
  invisible pour lui de toute façon.
- **Les mentions historiques** dans `CLAUDE.md`/`ROADMAP.md` qui narrent le
  passé ("ex-Orion", l'incident `orion3d_bridge.py` supprimé) — les
  réécrire effacerait l'historique du projet sans raison.

**Leçon de la session précédente, reconfirmée** : une première tentative par
expression régulière sur `\borion\b` avait transformé `self.orion` en
`self.luca's` — erreur de syntaxe immédiate, car l'apostrophe n'est pas
valide dans un identifiant Python. Cette fois, "Lucas" (sans apostrophe) sert
pour tout identifiant de code, "Luca's" (avec apostrophe) uniquement pour le
texte visible par Cyril (placeholders, messages, prose) — les deux formes
ont été distinguées à chaque remplacement, pas mélangées.

### Ce qui reste (ancien contenu de cette section — statut au 02/08/2026)

Renommage acté par Cyril le 29-30/07/2026, planifié pour après S2 stabilisé :
- ~~Titre fenêtre PySide6, prompts système du LLM, messages TTS~~ — fait le 01/08/2026
- Le nom du dossier projet (`C:\OrionAI` → autre chose) — **toujours optionnel,
  toujours différé**, voir la section technique ci-dessus pour le risque précis
- ~~Mise à jour de `CLAUDE.md`, `ROADMAP.md`, `IDEAS.md`~~ (remplacement des
  mentions "Orion"/"OrionAI" pour les références techniques encore valides) —
  fait le 02/08/2026, en gardant intactes les mentions qui narrent l'histoire
  du projet

---

## 7. Règles de mise à jour de ce fichier

- Après chaque brique validée : déplacer l'élément vers "État actuel ✅", repréciser la nouvelle étape immédiate.
- Ne jamais sauter une phase pour une fonctionnalité "fun" tant que le socle n'est pas stable.
- Toute nouvelle idée émergente va dans `IDEAS.md`, pas ici.
