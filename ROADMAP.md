# ROADMAP.md — Plan d'action Luca's AI (ex-OrionAI)

Référence croisée : voir `IDEAS.md` pour le détail complet de chaque fonctionnalité citée ici.

> **Mise à jour du 30/07/2026** : S1 (Cerveau solide — FastAPI unique) est officiellement validé de bout en bout. Prochaine étape : S2 (Mémoire enrichie, RAG, TTS, Finance CSV).
>
> **Renommage acté** : le projet s'appelle désormais **Luca's** (ex-Orion). Le renommage technique complet (titre fenêtre, prompts système, nom de dossier) est différé — pas urgent, sera fait une fois le socle S2-S3 stabilisé. Voir section 6.

---

## 1. État actuel (au 30/07/2026)

⚠️ **Section figée à sa date, non mise à jour depuis** — corrigé lors de
l'audit de cohérence documentaire du 02-03/08/2026 : plusieurs lignes
ci-dessous ont été rendues obsolètes par des chantiers documentés plus
loin dans ce même fichier, sans que cette section d'ouverture n'ait
jamais été mise à jour en retour. Gardée telle quelle comme repère
historique (« où on en était le 30/07 »), mais ne pas la lire comme
l'état courant — voir §2 à §6 pour ça.

### ✅ Modules validés et testés en conditions réelles
1. Chat avec streaming QThread (UI PySide6)
2. Mémoire persistante SQLite (`memory/orion_memory.db`) — confirmée comme seule source de vérité
3. FastAPI unique (`api/server.py` v0.2) — **testé de bout en bout aujourd'hui** :
   - `GET /status` ✅
   - `GET /system` ✅ (World Model v1 : CPU, RAM, fenêtre active via psutil + pywin32)
   - `POST /chat` ✅ (connecté à `OrionCore.ask()` → Ollama → réponse réelle, plus de stub)
   - `WS /ws` — endpoint créé, protocole minimal état/parole, **pas encore testé avec un vrai client** (Godot/mobile viendront en S6/S5)
     ⚠️ **Périmé** : `/ws` est depuis testé de bout en bout avec de vrais
     clients réels — PWA mobile (chat, micro, caméra, HTTPS), Godot. Voir
     §2 et §3 pour le détail complet, daté, de chaque chantier.
4. Modèle LLM confirmé en usage réel : `qwen2.5:7b` (via Ollama)
5. Avatar 2D QPainter (v2)

### ⚠️ Statut réel à clarifier (non re-testés depuis l'audit initial)
⚠️ **Résolu depuis, voir §5.2** : cette liste datait d'avant l'écriture
des tests de `rag_manager.py`, `vision_manager.py`, `automation_manager.py`
et `web_search.py`, qui en ont désormais — l'audit de fiabilité du
02/08/2026 l'a confirmé et republié la note à jour (§5.2, dernier
paragraphe) sans jamais revenir corriger CETTE section d'origine.
`weather_manager.py` était le seul réellement orphelin de test, corrigé
le même jour (voir §5.2, point 1). `finance_manager.py` n'a jamais fait
partie de la liste des orphelins réels d'après ce même audit.
- `modules/finance_manager.py`, `rag_manager.py`, `vision_manager.py`, `weather_manager.py`, `automation_manager.py`, `web_search.py` — à tester lors de S2/S3
- `Orion3D.exe` (Godot) — visage/fenêtre transparente fonctionne visuellement, mais `orion3d_bridge.py` fait uniquement écho, pas connecté à Ollama/OrionCore
  ⚠️ **Contexte historique uniquement** : `orion3d_bridge.py` a depuis été
  supprimé (voir `test_protocol.py`, « le pont mort est parti ») — Godot
  parle maintenant au même `/ws` que tout le reste, plus à un service à part.

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
| Mémoire enrichie | ✅ **Fait — coche manquante corrigée le 03/08/2026 (audit de cohérence documentaire), déjà construit et éprouvé bien avant cette date.** Historique de conversation (`fit_history_to_budget()`), contexte système (`world_model.format_for_prompt()` — CPU/RAM/heure/fenêtre active) et événements récents (`format_events_for_prompt()`) injectés dans `core/lucas_core.py::_build_messages()`. Testé (`test_memory_context.py`, `test_world_model.py`, `test_history_budget.py`) ET stress-testé en conditions réelles à plusieurs reprises depuis (c'est ce même mécanisme qui a révélé et fait corriger la dilution du prompt système sous historique chargé, §5.4, et le bug de décrochage OrangeTV plus haut dans ce document). |
| RAG documents personnels | ✅ **Fait et validé en conditions réelles (01/08/2026).** 39 documents de Cyril indexés, 229 morceaux. Point d'entrée `memory/index_documents.py` (relançable sans risque), lecture `.pdf` / `.docx` / texte, recherche hybride sémantique + date, seuil de pertinence calibré sur le corpus réel. Voir l'encadré ci-dessous. |
| TTS intégré au chat | ✅ UI PySide6 fait de longue date. **Pont mobile (PWA) fait et validé le 02/08/2026** — voir encadré ci-dessous. |
| Finance CSV | ✅ **Fermé le 03/08/2026.** Import + catégorisation existaient depuis longtemps (`modules/finance_manager.py`, `finance_categorizer.py`, 23 tests) mais n'étaient reliés à RIEN — aucune commande chat, aucune route API, aucune UI, alors que `SYSTEM_PROMPT` affirmait déjà cette capacité à Cyril. Voir l'encadré ci-dessous pour ce qui a été branché. |
| Mémoire — confiance & provenance | ⏳ **Pas commencé (ajouté 03/08/2026, voir `IDEAS.md` §2bis).** Enrichir le schéma SQLite mémoire avec confiance/provenance/date/expiration avant d'attaquer le Reasoning Engine — évite de bâtir un raisonnement sur des souvenirs non fiables. |

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

#### ✅ TTS — pont mobile (PWA) — terminé le 02/08/2026

`modules/voice_manager.py` et le routage local/cloud (`core.router.route_voice()`)
existaient déjà, mais uniquement branchés sur l'UI PySide6
(`ui/main_window.py`, `TTSWorker`) — l'API WebSocket n'envoyait jamais
d'audio en retour, et la PWA n'avait aucun code de lecture. Recommandé
par Claude Code comme prochaine étape naturelle du pont mobile (le
téléphone pouvait déjà écrire, parler et montrer une photo à Luca's,
mais jamais l'entendre répondre), validé par Cyril.

**Point d'architecture** : `VoiceManager.speak()` joue l'audio
*localement* (`pygame.mixer`, haut-parleurs du PC) — inadapté à la PWA,
qui doit jouer le son sur le téléphone. Nouvelle méthode publique
`synthesize_routed()` : route et synthétise SANS jouer, `speak()` en
devient un fin appelant (comportement bureau inchangé, tests existants
non touchés). Le serveur lit le fichier produit, l'encode en base64, et
le renvoie via un nouveau message `"speech"` — nommé ainsi et pas
`"audio"` pour ne pas entrer en collision avec le type ENTRANT `"audio"`
(micro du téléphone).

**edge_tts appelle `asyncio.run()` en interne** ; l'appeler tel quel
depuis le handler WebSocket (déjà dans une boucle asyncio active) aurait
levé une erreur. Résolu avec `asyncio.to_thread(...)`, qui exécute la
synthèse dans un thread séparé — même principe que `TTSWorker` (un
`QThread`) côté bureau, qui échappe au problème pour la même raison.

**Optionnel, désactivé par défaut** — bouton 🔊/🔇 dans la PWA
(`static/js/voice_output.js`), même défaut que le toggle « TTS Auto » de
l'UI PySide6 (`tts_auto = False`). Le texte part TOUJOURS en premier,
la synthèse ensuite : edge_tts prend plusieurs secondes (réseau), Cyril
ne doit pas attendre l'audio pour lire la réponse.

**Transparence** : la console de flux (#77) affiche maintenant aussi la
voix — synthétisée (et via quel moteur), non prononcée (contenu
sensible + Piper indisponible), ou en panne. Un événement TTS jamais
silencieux, cohérent avec le principe déjà appliqué au RAG et à l'écran.

**Validé en conditions réelles**, vrai serveur, vrai edge_tts, vrai
Piper — pas seulement en tests :

| Question | Routage | Résultat |
|---|---|---|
| « Quelle est la capitale de l'Italie ? » | cloud (edge_tts) | `audio/mpeg`, 38 016 octets, symbole MP3 valide |
| « Quel est mon salaire ce mois-ci ? » | local (Piper) | `audio/wav`, 752 684 octets, symbole RIFF/WAVE valide |

Le routage sensible/non-sensible déjà établi pour `route_voice()`
n'a pas été retouché — seulement branché sur un nouveau transport.

Tests : `test_protocol.py` (`speech()`, `read_speak_flag()`),
`test_server.py` (chemin heureux, refus silencieux annoncé, panne TTS
qui n'invalide pas la réponse texte, mime mp3/wav, image et audio
transcrit peuvent aussi être prononcés), `test_voice_router.py`
(`synthesize_routed()` délègue correctement).

##### Correctif : le son coupait en plein mot — fait le 02/08/2026

Signalé par Cyril en test réel : le son démarrait (« Bonj... ») puis
coupait net, sans erreur. Diagnostic par élimination (voir historique
git pour le détail complet des mesures) : `play()` créait `new Audio()`
en variable locale, jamais référencé ailleurs — éligible au
ramasse-miettes PENDANT la lecture. Corrigé en réutilisant un seul
élément conservé sur l'instance (`static/js/voice_output.js`).
Confirmé fonctionnel par Cyril après correctif.

##### Prérequis découvert : micro ET caméra exigent un contexte sécurisé — fait le 02/08/2026

En testant la voix, Cyril a signalé que le bouton micro échouait aussi
(« contexte non sécurisé »). Vérification : la caméra échouait avec
exactement le même message — pas un bug du micro, `getUserMedia()`
(micro ET caméra) refuse de fonctionner hors HTTPS ou `localhost`, et
une IP réseau en HTTP n'en est pas un. Ce n'est pas une régression :
l'entrée `IDEAS.md` du 02/08/2026 sur la PWA ne parlait que de la
« structure » micro/caméra testée, jamais d'une capture réellement
vérifiée — ce test l'a simplement révélé le premier.

**Décision de Cyril : vrai certificat HTTPS**, pas le contournement
rapide (`chrome://flags`, un réglage par appareil, à refaire si l'IP
change). `tools/mkcert.exe` (téléchargé directement — Chocolatey a
échoué faute de droits admin) génère une CA locale, installée dans le
magasin de confiance Windows (`mkcert -install`, a demandé une
confirmation Windows — geste que je ne dois jamais faire à la place de
Cyril, voir CLAUDE.md liste des actions interdites) puis un certificat
couvrant les deux IP réseau du PC (Ethernet 192.168.1.12, Wi-Fi
192.168.1.14) plus `localhost`/`127.0.0.1`. Ni `tools/mkcert.exe` ni
`data/cert.pem`/`data/key.pem` ne sont versionnés (`.gitignore`) — la
clé privée n'a rien à faire dans git, et le certificat est propre à
cette machine et son IP réseau.

`justfile` : `serve` sert maintenant en HTTPS sur `0.0.0.0` par défaut
(`serve-http` reste disponible pour un dépannage local sans certificat).
L'ancien commentaire justifiant `127.0.0.1` par « l'API n'a pas
d'authentification » ne tenait plus depuis `API_TOKEN` (voir plus haut,
02/08/2026) — corrigé au passage.

⚠️ **Le jeton API ne survit pas au changement d'origine.**
`http://192.168.1.14:8000` et `https://192.168.1.14:8000` sont deux
origines distinctes pour le navigateur — `localStorage` ne se partage
pas entre elles. Le lien avec `?token=...` doit être renvoyé une fois
pour la nouvelle origine HTTPS, exactement comme au tout premier envoi.

**La CA locale n'est installée que sur le PC.** Le téléphone de Cyril ne
fera pas confiance au certificat tant que la CA n'y est pas installée
aussi — `rootCA.pem` copié vers `static/rootCA.crt` (public, sans
risque à distribuer, contrairement à `rootCA-key.pem` qui ne quitte
jamais le PC) pour que le téléphone puisse le télécharger directement
depuis la PWA et l'installer via les réglages Android.

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

#### ✅ Finance CSV — fermé le 03/08/2026

**Trouvé en resynchronisant l'état réel du projet** (session autonome,
Cyril absent 7h30) : la ligne « Finance CSV » de Phase 2 n'avait jamais
de coche, et pour cause — `modules/finance_manager.py` (import CSV,
23 tests) et `modules/finance_categorizer.py` (catégorisation
règles+LLM local) étaient construits et testés depuis longtemps, mais
**reliés à rien**. Aucune commande chat ne les appelait, aucune route
API, aucune UI — alors que `SYSTEM_PROMPT` (`config.py`) affirmait déjà
à Cyril que Luca's « lit et catégorise des relevés bancaires importés en
CSV ». Une capacité annoncée mais qui n'existait pas dans les faits :
demander « importe mon relevé » n'aurait rien fait de réel.

**Câblé, pas réécrit** :

- `core/router.should_use_finance()` — déclencheur DÉTERMINISTE (liste
  `KEYWORDS_FINANCE`), pas un classifieur LLM comme `core/intent.py` : le
  domaine est plus étroit et moins ambigu que écran/documents, et rester
  déterministe évite de toucher un classifieur déjà calibré et fragile.
- `modules/finance_manager.load_directory()` — nouvelle fonction,
  importe tous les CSV de `data/finance/` (dossier réel de Cyril, déjà
  dans `.gitignore`, jamais créé sur le disque avant aujourd'hui).
  `use_llm=False` par défaut, à l'inverse d'un import manuel : ce chemin
  tourne à CHAQUE question financière du chat, pas une fois pour toutes.
- `core/lucas_core.py::_build_messages()` — bloc de contexte finance,
  jamais vers le cloud (même garde redondante que RAG/vision), même
  principe « ne jamais se taire » : dossier vide → message explicite
  interdisant d'inventer un solde, plutôt qu'un silence que le modèle
  comblerait.
- `GET /finance/summary` (api/server.py, même garde de jeton que
  `/history`/`/documents`) + panneau PWA « Mes finances »
  (`static/js/finance.js`, icône 💰) — lecture seule, même famille que
  le panneau Semantic Desktop du 03/08.

**Bug trouvé EN VALIDANT, pas en écrivant le code** : question réelle
posée à un vrai Ollama (qwen2.5:7b) sur des données réelles — « Résume
mes finances » a produit un résumé exact sur tout, SAUF la transaction
non catégorisée : le modèle a inventé « 447,10 € » là où le vrai montant
est -150,00 €. Cause : `get_summary()` listait cette transaction par
date + libellé, jamais son montant — un trou que le modèle a comblé
malgré la consigne explicite « n'invente jamais un montant » dans le
bloc injecté. Corrigé en ajoutant le montant réel à cette ligne
(`modules/finance_manager.py`) : plus rien à deviner, plus rien
d'inventé, revérifié sur le même vrai Ollama. Même famille de bug que la
« Non-Response » RAG déjà documentée ailleurs dans ce fichier — une
instruction ne protège pas contre un trou de données, seule l'absence du
trou le fait. 1 test de régression explicite.

**Validé en conditions réelles, pas seulement en tests** : le fixture
versionné `data/sample_transactions.csv` copié TEMPORAIREMENT dans
`data/finance/` (jamais les vraies données de Cyril, qu'il n'a pas
encore fournies) — instance uvicorn jetable, vrai Ollama, PWA ouverte
dans un vrai Chrome. Résultats identiques et exacts sur les trois
surfaces (chat, `/finance/summary`, panneau PWA) : solde 2198,87 €,
revenus 4800,00 €, dépenses 2601,13 €, répartition par catégorie, la
transaction non catégorisée avec son vrai montant. Question témoin
(« Quelle heure est-il ? ») confirmée SANS déclenchement du bloc
finance. Fichier de test retiré de `data/finance/` après validation —
le dossier reste vide jusqu'à ce que Cyril y dépose un vrai export.

**Ce qui reste ouvert, explicitement** : tout ceci n'a été validé que
sur des données FICTIVES (le fixture de test). La vraie validation —
est-ce que le format réel des relevés de Cyril s'importe sans erreur, la
catégorisation couvre-t-elle ses vraies dépenses — attend qu'il dépose
un export CSV réel dans `data/finance/`. Pas un « dashboard » séparé au
sens d'une page dédiée : le panneau PWA sert cet usage, cohérent avec le
patron déjà établi pour Semantic Desktop.

24 tests ajoutés au total (`test_router.py` : 13 dont `should_use_finance()`
et l'injection de contexte ; `test_finance.py` : 8 pour `load_directory()`
+ 1 régression montant ; `test_server.py` : 3 pour `/finance/summary`).
Suite complète rejouée sans régression.

---

## 3. Jalons futurs

| Phase | Semaine | Focus | Statut |
|---|---|---|---|
| **Phase 0 — Audit** | S0 | Nettoyage, inventaire | ✅ Fait (avec incident de suppression accidentelle résolu — voir CLAUDE.md) |
| **Phase 1 — Cerveau solide** | S1 | FastAPI unique + World Model | ✅ **Fait et validé aujourd'hui** |
| **Phase 2 — Mémoire & Finance** | S2 | RAG, TTS, Finance CSV | ✅ Fait — RAG et TTS le 01-02/08, Finance CSV câblé et validé le 03/08 (données fictives ; vraie validation attend un export réel de Cyril) |
| **Phase 3 — Vision & Voix** | S3-S4 | VLM écran, Avatar QPainter V3, 5 modes de présence, barge-in (voir IDEAS.md #83) | 🟡 En cours — VLM écran ✅, 5 modes de présence ✅, barge-in implémenté le 03/08/2026 (§5.4 point 5), pas encore validé en conditions réelles |
| **Phase 4 — Expansion** | S5-S6 | PWA mobile, sync, Godot 4 V1 (branche expérimentale) | 🟡 Amorcé — côté serveur du pont audio branché (02/08), PWA/auth/tunnel restent à faire |
| **Phase 5 — Polish** | S7-S8 | Sécurité finale, packaging, release v1.0 | À venir |

### Hors tableau — Decision Engine, pas encore planifié (ajouté 03/08/2026)

**Cartes d'approbation (ALLOW/DENY)** et **STOP mid-tool-call**
(`IDEAS.md` #80 et #81) : exigences UX pour la future liste blanche
Self-Decision. Volontairement absentes du tableau ci-dessus — aucune de
ses phases ne les couvre. `core/decision_engine.py` n'existe pas encore
(voir la structure de dossiers de `CLAUDE.md` — planifié, pas construit) ;
le seul mécanisme de liste blanche réel aujourd'hui est
`modules/automation_manager.py`, au périmètre plus étroit (lancer une
appli). « OS Controller + Automation » apparaît dans la liste **S1-S8**
de `CLAUDE.md` (S6) — une numérotation distincte de ce tableau de
Phases, pas une deuxième mention du même jalon.

À rattacher à une phase (probablement Phase 4 ou une future Phase 6, à
créer) quand ce chantier sera réellement planifié — pas avant.

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

> **Note de numérotation — harmonisée le 02-03/08/2026.** Ce tableau place le pont mobile en **Phase 4** (semaines S5-S6). Les mentions « Phase 5 » dans `config.py`, `README_INSTALL.md` et `stt_engine.py` (écrites le 01/08, reprenant le libellé de semaine) ont été corrigées en « Phase 4 » pour suivre ce tableau.
>
> **Désaccord de séquençage résolu par les faits, pas par un simple remplacement de texte** : la section « Priorités de Développement » de `CLAUDE.md` situait le « Mobile Bridge » en **S7**, après OS Controller/Automation — en contradiction avec ce tableau (Phase 4 = S5-S6, avant). La question posée ici (« quand le pont mobile passe-t-il réellement ? ») a une réponse maintenant : il a été construit et livré en entier (chat, micro, caméra, TTS, HTTPS) le 02/08/2026, immédiatement après S2 (Mémoire & Finance) et en parallèle de la Phase 3 (Vision), **avant** tout travail sur OS Controller/Automation — jamais commencé. `CLAUDE.md` corrigé en conséquence pour refléter ce qui s'est réellement passé, pas une préférence de planning a priori.

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
3. **Le protocole de tunnel — ✅ tranché par Cyril le 03/08/2026 : Tailscale**,
   plutôt que WireGuard brut. Raisons données : simplicité pour un
   débutant, gestion automatique de l'IP dynamique, chiffrement de bout en
   bout conservé (seules les métadonnées de coordination transitent par le
   serveur Tailscale, jamais le contenu). `VISION_LONG_TERME.md` §2
   Pilier 3 laissait la question explicitement ouverte (« à définir en
   Phase Mobile ») — c'est fait, mais **pas implémenté** : Phase 4 n'est
   pas le chantier actif aujourd'hui (voir §5.4/§5.6 et la liste priorisée
   de la resynchronisation du 03/08/2026), cette décision attend juste que
   Phase 4 redevienne prioritaire pour être exécutée.

   **Préparé le 03/08/2026, audité avant d'agir** : `config.py`/`api/server.py`
   ne dépendent d'aucune IP en dur (`API_HOST="0.0.0.0"`, CORS déjà
   `allow_origins=["*"]`, la PWA construit son URL depuis
   `location.host`) — rien à recoder pour accueillir une IP Tailscale.
   Seul le certificat HTTPS (`data/cert.pem`, SAN limités aux IP LAN
   actuelles) devra être régénéré avec l'IP/nom Tailscale une fois connu
   — procédure documentée dans `justfile`. **Bloqué sur deux actions que
   seul Cyril peut faire** : installer le client Tailscale et
   s'authentifier (`tailscale up`, connexion de compte) sur le PC et le
   S25 Ultra — hors de portée d'un agent autonome (comptes/identifiants).

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

### 🟢 Session du 02/08/2026 (suite) — API ouverte au réseau, premier test téléphone

À la demande explicite de Cyril : `API_HOST` passé de `127.0.0.1` à
`0.0.0.0` dans `config.py`, pour que le S25 Ultra puisse joindre l'API.

**Fait dans le même geste, avant l'ouverture réseau, jamais après** :
`.env` créé (n'existait pas encore) avec un `API_TOKEN` réel généré
(`secrets.token_urlsafe`). Sans ce préalable, ouvrir `0.0.0.0` aurait
rendu tout l'historique de conversation lisible par n'importe quel
appareil du WiFi sans rien prouver — exactement le risque documenté
depuis le 01/08 (§5.1) et repris lors de la construction du jeton plus
tôt aujourd'hui (§2 ci-dessus).

**Ajout côté PWA** : `static/js/app.js` lit maintenant un `?token=...`
dans l'URL au chargement, le range dans `localStorage`, puis le retire
de l'URL (`history.replaceState`) — pour configurer le téléphone en un
seul lien ouvert, sans écran de réglages à construire pour l'instant.

**⚠️ Bug de test trouvé et corrigé en marge de ce changement** : créer un
vrai `.env` avec un vrai `API_TOKEN` a fait échouer 27 tests d'un coup —
la suite supposait silencieusement `API_TOKEN` vide par défaut, ce qui
n'était vrai que tant qu'aucun `.env` réel n'existait sur la machine. Un
test ne doit jamais dépendre du contenu réel de `.env` du poste où il
tourne. Corrigé par une fixture `autouse` dans `test_server.py`
(`_no_token_by_default`) qui force `api.server.API_TOKEN` à `""` avant
chaque test ; les tests qui veulent un vrai jeton le posent eux-mêmes
via `monkeypatch`, qui prévaut pour la durée du test. 605/605 après
correction.

**Vérifié depuis le PC** (pas encore depuis le téléphone lui-même à
l'écriture de cette note) : IP locale obtenue (`192.168.1.14` en WiFi,
`192.168.1.12` en Ethernet — même sous-réseau), `GET /status` répond en
`200` sans jeton (endpoint non protégé), `GET /system` répond `401` sans
jeton et `200` avec, `GET /app/` sert la PWA — le tout via l'IP LAN, pas
seulement `127.0.0.1`.

**Non vérifié, hors de portée depuis cet environnement** : le test
depuis le téléphone lui-même — nécessite que Cyril ouvre l'URL sur le
S25 Ultra, aucun outil ici ne peut piloter son téléphone. Deux blocages
possibles à anticiper s'il ne se connecte pas du premier coup :
- **Pare-feu Windows** : aucune règle dédiée trouvée pour le port 8000 au
  moment de la vérification (lecture seule — jamais modifié, une
  modification de pare-feu est une action interdite pour Claude Code,
  voir CLAUDE.md). Si Windows affiche une invite « autoriser python.exe
  sur les réseaux privés », c'est à Cyril de répondre.
- **Micro/caméra resteront inutilisables depuis le téléphone tant que
  l'accès se fait en `http://` simple** : `getUserMedia()` exige un
  contexte sécurisé (HTTPS, ou `localhost`) — une IP locale en clair ne
  l'est pas. Le chat fonctionnera, pas les boutons micro/caméra. Prévu
  et documenté dès `static/js/audio.js`, confirmé structurel ici : il
  faudra du TLS, pas seulement le jeton, avant un vrai usage mobile complet.

### 🔴 Bug trouvé par Cyril, corrigé — vision écran PC déclenchée par erreur depuis le téléphone

**Premier vrai test mobile : succès partiel.** Le chat texte a fonctionné
de bout en bout (réponse cohérente reçue sur le téléphone), mais "que
peux-tu voir sur mes écrans ?" envoyé en texte depuis la PWA a capturé
et décrit l'écran du PC — alors que la question venait du téléphone,
sans bouton caméra.

**Cause** : `should_use_vision()` classe l'INTENTION du texte (« ça parle
d'écran »), pas la provenance. Le même texte, tapé dans Godot (toujours
sur ce PC) ou envoyé depuis la PWA (peut-être loin de ce PC), déclenchait
la même capture silencieuse — une vraie faute de confidentialité, pas un
détail technique : la protection WATCHING existe précisément pour que
personne ne regarde l'écran de Cyril sans qu'il le sache.

**Corrigé en deux temps, à la demande de Cyril** :

1. **Protection contre le déclenchement accidentel.** `api/server.py`
   retient maintenant le client annoncé par le "hello" (`lucas_pwa` ou
   non). `core/lucas_core.py` : `ask()`/`_build_messages()` acceptent
   `allow_screen_capture` — à `False` pour la PWA, le classifieur tourne
   toujours (pour savoir si l'intention était l'écran) mais la capture
   est refusée, et Luca's l'explique au lieu de se taire (même principe
   que le RAG sans résultat) : *"tu N'AS PAS regardé l'écran du PC pour
   cette demande, volontairement... propose le bouton caméra"*.
2. **Override explicite, pour ne pas sur-corriger.** Nommer le PC sans
   ambiguïté (« mon PC », « mon ordinateur », « sur l'ordi »…) lève la
   restriction même depuis la PWA — `mentions_pc_explicitly()`
   (`core/router.py`), mots-clés déterministes, **jamais de
   classification LLM** : même raisonnement que `is_sensitive()`, se
   tromper ici capturerait l'écran sans demande claire. WATCHING reste
   le témoin FIDÈLE de la vraie capture (`api/server.py` vérifie aussi
   `mentions_pc_explicitly()` pour l'état de l'avatar, pas seulement le
   type de client).

**Bug de test trouvé EN CONSTRUISANT le correctif** : `_FakeCore` dans
`test_server.py` n'avait jamais défini `recent_context()` — chaque test
qui passait par ce double et appelait `should_use_vision(message,
lucas.recent_context())` levait silencieusement une `AttributeError`,
rattrapée par le `except` large d'`api/server.py`, qui retombait toujours
sur `regarde=False`. Aucun test n'avait donc jamais pu vérifier l'état
`WATCHING` via ce fixture — le trou s'est révélé au premier test qui
l'exigeait vraiment. Corrigé.

**Validé** : 15 nouveaux tests (`test_router.py` pour
`mentions_pc_explicitly()` seule, `test_vision_routing.py` pour le
comportement `_build_messages`, `test_server.py` pour le cycle complet
avatar). 627/627 sur la suite complète. Confirmé en conditions réelles,
API relancée : le même texte ambigu redonne bien `thinking` (Luca's
explique qu'elle n'a pas regardé), et « montre-moi ce qui est affiché
sur mon PC » redonne bien `watching` avec une description exacte de
l'écran réel, vérifié sur une conversation isolée (les deux essais
menés via le websocket réel ont ajouté deux échanges dans
`memory/lucas_memory.db`, la même base que le téléphone de Cyril — sans
donnée sensible, mais signalé pour transparence).

### 🔴 Bug trouvé par Cyril, corrigé — SYSTEM_PROMPT n'ancrait à rien de réel

**Deuxième retour de test mobile.** Sur des questions ouvertes du type
« que voudrais-tu améliorer, que souhaites-tu vraiment ? », Luca's
inventait des réponses génériques sans rapport avec le projet — accès
Gmail/Outlook, authentification multi-facteurs — rien de tout ça
n'existe ni n'est prévu.

**Cause** : `config.SYSTEM_PROMPT` tenait en deux phrases (« Tu es
Luca's, l'assistant personnel de Cyril... réponds en français »), sans
une seule capacité listée. Sans rien pour l'ancrer, le modèle retombait
sur des clichés d'« assistant IA » appris à l'entraînement dès qu'une
question sortait du cadre habituel.

**Corrigé** : `SYSTEM_PROMPT` réécrit avec une liste de capacités
POSITIVE (finance CSV, documents/RAG, écran/OCR, voix, sécurité niveau
1 — observation seule) ET NÉGATIVE (pas de messagerie/agenda, pas de
MFA, pas de navigation autonome, pas de commandes arbitraires), plus la
brique en cours (pont mobile). La liste négative cible directement le
bug signalé : nommer explicitement ce qui n'existe PAS empêche le
modèle de l'inventer. Dernière ligne dédiée aux questions méta
(« qu'est-ce que tu voudrais » ) : répondre à partir de cette liste,
jamais en inventant des capacités génériques.

Contenu tiré du code livré (`modules/finance_manager.py`,
`automation_manager.py`, l'état réel de `security/` dans ce fichier),
pas de l'ambition long terme de `VISION_LONG_TERME.md` — le modèle n'a
aucun moyen de distinguer « construit » de « rêvé » si le prompt ne le
fait pas pour lui. À tenir à jour à chaque capacité livrée ou retirée,
comme documenté dans le commentaire de `config.py`.

**Validé** : 627/627 sur la suite complète (aucun test n'asserte sur le
contenu littéral du prompt). Testé en conditions réelles sur une
conversation isolée avec la question exacte remontée par Cyril : plus
aucune mention de Gmail/Outlook/MFA, réponse ancrée dans les vraies
capacités (documents, finance), toute extension proposée formulée comme
un souhait explicite, jamais comme une capacité déjà existante.

---

## 4. Principe directeur

> **"Cerveau solide d'abord, visage beau ensuite. Mais le visage ne part jamais."**

Architecture serveur validée aujourd'hui : une seule API FastAPI, `/ws` unique partagé par Godot et mobile (futur), routes REST classiques. Pas de serveur dupliqué.

Sécurité validée : **liste blanche et confirmation pour toute action système à risque** — pas un bridage par défaut de tout le reste. Luca's a un accès large et réel à ce dont elle a besoin pour être utile ; c'est au moment du doute ou du risque qu'elle demande, et Cyril tranche. Jamais de script généré dynamiquement par le LLM, jamais d'exécution de code auto-généré hors sandbox. Formulation de référence : `VISION_LONG_TERME.md` §4 — en cas d'écart entre les deux fichiers, c'est la vision qui fait foi.

**État de `security/` au 01/08/2026 — niveau 0, observation seule.** Guardian, Privacy Shield et Ransomware Watch existent en ébauche testée (62 tests) : ils détectent et rapportent, ils n'agissent jamais. Aucun process tué, aucune connexion coupée, aucun fichier restauré, aucun appel à un service externe. Leur donner un pouvoir d'action défensif est une décision distincte, à valider par Cyril.

La détection de rançongiciel repose sur les **métadonnées seules** (extensions connues, notes de rançon, rafale de modifications) et sur des **fichiers-appâts** déployés explicitement. Elle ne lit jamais le contenu des documents aujourd'hui : l'analyse d'entropie, plus fiable mais qui obligerait le capteur à ouvrir les fichiers personnels, a été **acceptée par Cyril le 03/08/2026** — scopée à un déclenchement événementiel, jamais un balayage permanent (voir plus bas, « Niveau 1 » et `security/ransomware_watch.py`) — mais pas encore construite.

**Surveillance continue branchée sur le daemon** (01/08/2026) : `SecurityMonitor` orchestre les trois capteurs depuis `orion_daemon.py` — process et réseau toutes les 5 minutes, fichiers toutes les 15. Les signaux ne sont rapportés qu'une fois : un état persistant (`data/security_state.json`) déduplique d'un balayage à l'autre et d'un redémarrage à l'autre, et oublie un signal après 3 jours d'absence pour que son retour soit de nouveau une information. Les alertes atterrissent dans `system_events`, donc dans le contexte que Luca's injecte au LLM.

**Niveau 1 livré le 01/08/2026 — les capteurs ont une mémoire.** `security/history.py` retient ce que la machine a l'habitude de faire, et deux capteurs s'en servent :

- **Premier contact externe** : un programme qui contacte une adresse publique pour la première fois est signalé. La clé retenue est (programme, IP) sans le port — les ports source changent à chaque connexion, les inclure ferait tout paraître nouveau.
- **Persistance au démarrage** (`security/persistence_watch.py`) : lecture des clés `Run`/`RunOnce` du registre et du dossier Démarrage. CRITIQUE si l'entrée pointe vers un répertoire temporaire, WARNING si elle est apparue depuis le dernier balayage. Le module lit le registre, il n'y écrit jamais.

**Période d'apprentissage de 24 h** (`SECURITY_LEARNING_HOURS`) : les capteurs observent sans alerter au démarrage. Mesuré sur cette machine, sans elle : **27 alertes au premier balayage** — chaque navigateur et application contactant Internet. Le rapport aurait été illisible et abandonné.

⚠️ **Sur les hooks clavier** : `ROADMAP` annonçait « suivi des hooks clavier (keylogger) ». Ce n'est **pas observable depuis Python de façon portable** — énumérer les hooks `SetWindowsHookEx` demande des appels natifs Win32 que `psutil` n'expose pas. Un module nommé « détecteur de keylogger » qui ne détecte rien donnerait une fausse assurance, exactement ce que §4.1 cherche à éviter. La détection de persistance vise le même adversaire par un angle réellement observable : un keylogger doit survivre au redémarrage.

**Niveau 1 clos le 01/08/2026.** Cinq capteurs (`guardian`, `privacy_shield`, `ransomware_watch`, `persistence_watch`, `monitor`), une mémoire partagée (`history`), 94 tests. Les chemins d'état sont ancrés sur la racine du projet — le daemon étant prévu en service Windows via NSSM, un chemin relatif faisait repartir l'apprentissage de zéro à chaque lancement.

**Les deux paliers ci-dessous ne partagent plus le même statut depuis le
03/08/2026 — décisions tranchées par Cyril :**

- **Analyse d'entropie des fichiers — ✅ ACCEPTÉE, mais scopée.** Pas un
  balayage permanent du disque (ça reviendrait à ouvrir tous les documents
  personnels en continu) : un **watcher événementiel**, qui ne mesure
  l'entropie que sur une rafale d'écritures/renommages massifs en peu de
  temps — le signal que `ransomware_watch.py` détecte déjà par métadonnées
  sert de déclencheur, l'entropie vient confirmer plutôt que surveiller
  seule. Décision actée, **prête à être développée quand ce chantier sera
  priorisé** — pas une action immédiate (voir `security/ransomware_watch.py`
  et `IDEAS.md` #84 pour le détail).
- **Détection native des hooks clavier (keylogger) — ❌ reste GELÉE
  indéfiniment**, pas juste en attente. Deux raisons cumulatives : la
  limite technique déjà documentée ci-dessus (`SetWindowsHookEx` hors de
  portée de `psutil`, donc hors de portée d'un mécanisme portable) ET,
  précisé par Cyril le 03/08/2026, un risque de **faux positifs
  antivirus** — le mécanisme bas niveau qu'exigerait une vraie détection
  ressemble structurellement à ce que Windows Defender surveille chez un
  vrai keylogger, avec un rapport effort/protection défavorable face au
  risque ransomware pour un usage personnel. Contrairement à l'analyse
  d'entropie, ce palier ne redeviendra pas un chantier à programmer un
  jour : c'est une exclusion, pas une pause.

`security/` reste donc au **niveau 1** tant que l'entropie n'est pas
construite — ce qui suffit au principe §4.1 pour les extensions
d'autonomie envisagées à court terme, mais pas pour un pouvoir d'action
défensif.

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

### Le prompt système se dilue aussi — troisième visage du même bug (02/08/2026)

Signalé par Cyril en usage réel : la liste des capacités venait d'être écrite dans `SYSTEM_PROMPT`, elle fonctionnait sur une conversation neuve, et restait sans effet sur la sienne. Les deux plafonds existants (`SOURCE_HISTORY_MESSAGES`, `CLOUD_HISTORY_MESSAGES`) ne s'appliquaient que quand une source externe était injectée ou que la requête sortait de la machine ; une **question ordinaire** recevait les 100 messages, et le prompt système s'y noyait exactement comme s'y noyait le bloc vision.

- **Ce n'est pas propre à une question, et c'est ce qui interdisait de corriger au cas par cas.** Mesuré sur deux règles indépendantes du prompt — une d'identité (« que voudrais-tu améliorer ? » doit citer une capacité réelle) et une **de sécurité** (« consulte ma boîte mail » doit être refusé). Les deux tombent de **9/9 sans historique à 1/9 et 2/9 sous 100 messages**. Une règle de sécurité se dilue aussi facilement qu'une règle de style.
- **Ce qui décide est le VOLUME de texte, pas le nombre de tours.** 30 messages tronqués à 150 caractères (5 809 car.) tiennent mieux tête au prompt système que 6 messages bruts (10 487 car.), en gardant cinq fois plus de contexte. D'où `HISTORY_BUDGET_CHARS` (budget en caractères) plutôt qu'un plafond en messages — c'est la mesure qui impose la forme du correctif, pas l'esthétique.
- **Répéter le prompt système avant la question aide, mais ne suffit pas.** Une instruction **factuelle** (« tu n'as pas accès aux mails ») se rattrape par répétition : 2/9 → 7/9. Une instruction qui lutte contre le **fil thématique** de la conversation, non : 1/9 → 1/9. Le ré-ancrage complète le budget, il ne le remplace pas.
- **Aucun réglage de prompt ne renverse une mauvaise réponse déjà donnée à la même question.** Sur la base réelle : 3/9 avec l'historique tel quel, **8/9 en supprimant quatre messages** — la même question déjà posée deux fois et ses deux réponses génériques. D'où `just forget-last`. Le budget empêche une mauvaise réponse d'en contaminer cent ; il ne peut pas effacer celle qui vient d'être donnée.
- **Tout motif régulier ajouté à l'historique devient un exemple à imiter — y compris la forme.** La première version terminait les messages tronqués par « […] ». Trouvé en test réel via l'API, pas en test unitaire : le modèle **recopie le marqueur** et coupe sa propre réponse en plein mot (« 2. \*\*Interfa […] »). 1/9 avec, 0/9 sans. La troncature se fait désormais sans marqueur et sur une frontière de mot.

⚠️ **Le trou était protégé par un test.** `test_history_is_kept_whole_without_vision` affirmait « le raccourcissement ne vaut QUE pour la vision, une conversation ordinaire garde sa mémoire longue » — et validait donc les 100 messages bruts qui cassaient le prompt système. Un test peut consacrer un bug autant qu'il peut le prévenir ; celui-ci a été réécrit pour dire ce qui reste vrai (une conversation ordinaire garde **plus** de contexte qu'une question sur l'écran), pas « tout, sans limite ».

Constantes et tableaux de mesure complets : `config.py` (`HISTORY_BUDGET_CHARS`). Implémentation : `fit_history_to_budget()` dans `core/lucas_core.py`. Tests : `test_history_budget.py`.

#### Ce que le correctif ne pouvait pas régler : la limite du modèle (tranché le 02/08/2026)

Le correctif appliqué, Cyril a retesté depuis son téléphone : réponse encore générique. Le correctif n'était pas en cause — il était **nécessaire mais pas suffisant**. Sur les questions ouvertes et introspectives (« que voudrais-tu améliorer ? »), `qwen2.5:7b` produit du discours d'assistant IA quel que soit l'historique, y compris sur une conversation vierge.

Mesuré sur la base réelle, question identique, critère de Cyril (réponse **ancrée dans les vraies capacités ET non générique**) :

| Modèle | Taille | Réponse ancrée | Question courte |
|---|---|---|---|
| `qwen2.5:7b` (retenu) | 4,7 Go | 1/5 | 2,7 s |
| `gemma4` | 9,6 Go | 4/5 | 5,3 s |
| `qwen3.6` | 23 Go | 4/5 | 16,1 s |

**Décision de Cyril : rester sur `qwen2.5:7b`.** La réactivité prime sur la qualité des réponses introspectives, qui ne sont pas le cœur de l'usage. À rouvrir si le sujet redevient gênant — les chiffres ci-dessus évitent d'avoir à re-mesurer. ⚠️ `qwen3.6` dépasse les 16 Go de VRAM de la RTX 5080 : les 16 s reflètent un débordement CPU, et il évincerait vision et embeddings de la carte.

⚠️ **Leçon de méthode, à retenir plus que le résultat.** Deux exécutions d'une condition identique ont donné 4/9 puis 7/9 : à cette finesse, la variance du modèle dépasse l'effet cherché, et 9 tirages ne tranchent plus rien. Les écarts francs (9/9 contre 1/9 sur la dilution, 1/5 contre 4/5 entre modèles) restent solides. **Ne pas conclure sur un écart de 2 ou 3 points à 9 tirages** — c'est du bruit présenté comme une mesure.

⚠️ **Un critère de mesure peut ne pas mesurer ce que Cyril voit.** Le premier critère comptait la *présence* d'une capacité réelle dans la réponse ; Cyril, lui, juge la *dominance* du discours. Une réponse citant « relevés bancaires » au milieu de cinq paragraphes sur l'apprentissage proactif passait le test automatique et restait générique à la lecture. Vérifier qu'un critère automatique s'aligne sur le jugement réel avant de s'appuyer dessus.

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

## 5.4 Backlog de polish identifié en usage réel — 02/08/2026

Remonté par Cyril pendant le test du pont mobile TTS, explicitement noté
comme **non urgent** par lui-même au moment du signalement — traité après
les vrais bugs bloquants (coupure audio TTS, caméra qui s'éteint seule,
tous deux corrigés le 02/08/2026, voir §2).

1. **Transcription du micro imprécise** — ✅ **Corrigé le 03/08/2026** (en
   autonomie, pendant l'absence de Cyril). Mesuré avant de conclure :
   script jetable synthétisant une phrase de référence connue via Piper
   (donc un texte de vérité terrain exact), réencodée en WebM/Opus via
   PyAV — même conteneur/codec que `MediaRecorder` sans `mimeType`
   explicite dans `static/js/audio.js` — puis transcrite dans plusieurs
   conditions et comparée au texte de référence (WER).

   Hypothèses éliminées par la mesure (aucun effet observé, sur deux
   phrases, à plusieurs niveaux de bruit) :
   - **Le suffixe `.wav` codé en dur** dans `transcribe_base64()` alors
     que le contenu réel est du WebM/Opus (`api/server.py` appelle
     `transcribe_base64(audio_base64)` sans préciser `suffix`) : faster-
     whisper (via PyAV) lit le contenu réel du fichier, pas son extension
     — sortie strictement identique avec `.wav` ou `.webm`. **Pas un bug.**
   - `language=None` (auto-détection) vs `"fr"` forcé : texte transcrit
     identique dans tous les cas, seule la métadonnée de confiance change.
   - `vad_filter=True` : aucun effet, ni sur audio propre, ni bruité, ni
     avec un silence ajouté en tête/queue (simulant le temps entre l'appui
     sur le bouton micro et le début de la phrase).
   - `initial_prompt="Luca's"` (pour corriger l'homophone ci-dessous) :
     **aggrave** le résultat — le modèle omet parfois le mot plutôt que de
     le mal orthographier. Abandonné.

   Cause réelle, mesurée : `STT_MODEL_SIZE = "base"` (`config.py`) perd
   nettement en précision sous bruit de fond réaliste (SNR 5 dB, un micro
   de téléphone dans une pièce) — WER 0,27 à 0,42 selon la phrase — alors
   que `"small"` reste correct ou quasi (WER 0,00 à 0,09) sur les deux
   mêmes phrases et les mêmes fichiers audio. Coût : ~0,8 s de calcul CPU
   au lieu de ~0,3 s, négligeable pour un message vocal non temps réel.
   `config.py` documentait déjà cette bascule comme une intention pour la
   v1.1 (`« small »... envisagé en v1.1`) — la mesure la rend justifiée
   dès maintenant plutôt que d'attendre. **`STT_MODEL_SIZE` passé à
   `"small"`.**

   Limite distincte constatée, non corrigée (pas un bug de pipeline) :
   **« Luca's » est systématiquement mal transcrit** (« Lucas »,
   « Loucause », « L'occose »...) par les deux tailles de modèle, à tous
   les niveaux de bruit — une ambiguïté homophone réelle que l'audio seul
   ne permet pas de lever (rien à l'oreille ne distingue « Luca's » de
   « Lucas »), et que `initial_prompt` ne corrige pas (voir ci-dessus).
   Une correction textuelle post-transcription serait possible (renommer
   « Lucas » en « Luca's » en début de phrase) mais risquerait des faux
   positifs (Cyril parlant d'un vrai Lucas). **Décision explicitement
   reportée par Cyril le 03/08/2026, pas abandonnée** : à trancher
   seulement après un vrai test du pipeline STT avec le speakerphone
   (matériel en commande à cette date) — c'est le seul moyen de savoir
   si l'ambiguïté gêne réellement à l'usage, plutôt que de deviner sur
   des mesures synthétiques (Piper).
2. **Lecture d'écran smartphone à affiner** — retour vague de Cyril
   (« il y a encore matière à travailler dessus »), à préciser avec lui
   avant d'agir.
3. **Bouton haut-parleur sans vrai mode mute** — ✅ **Corrigé le
   03/08/2026**, à la suite directe du travail sur le barge-in (point 5) :
   `VoiceOutput.stop()` existait déjà pour couper la lecture en cours,
   il ne restait qu'à le brancher sur le toggle 🔊/🔇 lui-même — passer en
   🔇 coupe désormais immédiatement un son déjà en train de jouer, pas
   seulement les réponses suivantes. Non testé en conditions réelles pour
   la même raison que les points 1 et 5 (pas de micro/haut-parleur
   physique sur cette machine), mais ce point précis (couper un `<audio>`
   HTML au clic) ne dépend d'aucun matériel — bien plus simple à faire
   confiance sans test réel que le barge-in.
4. **Dialogue perçu comme « compliqué »** — retour UX général de Cyril,
   pas encore de cause précise identifiée.
5. **Pas d'interruption immédiate (« barge-in »)** — ⚠️ **Conçu et
   implémenté le 03/08/2026** (en autonomie), **mais pas testé en
   conditions réelles** — cette machine n'a pas de micro (même contrainte
   que pour le STT, point 1 ci-dessus), donc rien de sonore n'a pu être
   validé de bout en bout ici. À vérifier par Cyril sur le S25 Ultra avant
   de considérer ce point clos.

   Mécanisme (`static/js/voice_output.js`) : pendant la lecture d'une
   réponse vocale (`VoiceOutput.play()`), un flux micro dédié s'ouvre via
   `getUserMedia` (`echoCancellation: true`, `noiseSuppression: true`,
   `autoGainControl: false` — l'AGC aurait faussé le seuil fixe en
   amplifiant le bruit de fond) et une `AnalyserNode` (Web Audio API)
   calcule un volume RMS à chaque frame. Au-delà d'un seuil
   (`BARGE_IN_RMS_THRESHOLD = 0.09`) pendant plusieurs frames consécutives
   (anti faux-positif sur un bruit bref), la lecture s'arrête
   immédiatement (`VoiceOutput.stop()`) et une ligne apparaît dans la
   console d'activité. Le flux micro est fermé dès la fin de la lecture
   (naturelle ou interrompue) — jamais ouvert en dehors des instants où
   Luca's parle, même principe de sobriété d'écoute que CLAUDE.md règle 3
   appliqué côté client.

   **Risque connu, non vérifiable ici** : sans annulation d'écho fiable,
   le micro pourrait capter la propre voix de Luca's sortant du
   haut-parleur du téléphone et se couper elle-même en boucle.
   `echoCancellation: true` est censé y répondre, mais son efficacité pour
   un `<audio>` lu hors WebRTC (pas un `RTCPeerConnection`) dépend du
   navigateur/device — c'est le point le plus susceptible d'exiger un
   réglage du seuil ou une autre approche après un vrai test.

   Volontairement laissé hors de ce chantier : un vrai bouton mute pour
   couper un son déjà en cours à la demande (point 3 ci-dessus, backlog
   distinct) — `VoiceOutput.stop()` existe maintenant et pourrait le
   servir directement, mais le brancher sur le bouton 🔊/🔇 n'a pas été
   demandé ici.

Voir aussi `IDEAS.md` pour l'idée distincte du double destinataire
WebSocket (parler au micro du téléphone et faire répondre l'avatar PC
en même temps) — une extension du pont mobile, pas un correctif.

## 5.5 🔴 Bug de fond ouvert (02/08/2026) — dérive complète de sujet sous historique chargé

Trouvé en diagnostiquant le bug « OrangeTV » (§ correctif vision
ci-dessus, voir git log), en rejouant le contexte réel exact de Cyril :
demandé de décrire une photo (bouton caméra), le modèle a répondu
**au sujet précédent de la conversation** (« je n'ai pas accès à votre
nom ou votre adresse ») au lieu de la question posée — 4 tirages sur 4,
avec ou sans le correctif « par exemple » ci-dessus, qui ne peut rien y
faire puisque le modèle n'atteint même pas le bloc d'instruction.

**Distinct de l'auto-imitation déjà documentée** (config.py,
`HISTORY_BUDGET_CHARS`, `REANCHOR_SYSTEM_PROMPT`) : celle-là faisait
imiter une réponse *au même sujet* ; ici le modèle change complètement
de sujet, en répondant à une question d'il y a plusieurs tours plutôt
qu'à celle qu'on vient de lui poser. Le ré-ancrage du prompt système
juste avant la question (déjà en place) ne suffit pas à empêcher ça —
la question elle-même semble se faire noyer, pas seulement les règles
du prompt système.

**Reproduit avec de vraies mesures**, pas une supposition : contexte
reconstruit depuis une copie de la vraie base de Cyril (troncature à
l'état exact avant l'échange concerné), rejoué contre le vrai modèle
local, 4/4 tirages dérivant sur le mauvais sujet.

**Non traité** — Cyril a choisi de le garder en note plutôt que d'agir
maintenant. Probablement lié au même mécanisme de troncature
d'historique (`fit_history_to_budget()`, `core/lucas_core.py`) que les
correctifs précédents, mais la piste reste à instruire : est-ce la
fenêtre de troncature qui laisse passer un tour trop saillant (comme
pour l'auto-imitation), ou autre chose de spécifique au changement de
sujet complet ? À reprendre avec le même protocole de mesure que les
bugs précédents (reconstruction sur copie de base réelle, tirages
multiples, isolation par historique vierge) avant tout correctif.

## 5.6 ✅ Vision/intent — DEUX aspects désormais résolus (câblage ET auto-imitation)

**Historique.** Cyril a signalé un « comportement KO » en déclenchant la
vision, sans jamais pouvoir transmettre la description complète du
symptôme ni le contenu réel d'un log — ses messages de suivi se sont
coupés à chaque tentative. Une instrumentation de debug a été posée le
jour même (`logging.basicConfig` dans `main.py`, `logger.debug()` dans
`ui/main_window.py`, `core/router.py`, `core/intent.py`,
`core/lucas_core.py`), puis retirée (686/686 tests verts) faute de
reproduction — **mis en pause volontairement, pas abandonné.**

### Aspect 1 — le câblage : confirmé correct, pas la cause

Repris dans une session suivante avec un vrai test (pas unitaire) :
chaîne tracée de bout en bout (`ui/main_window.py` → `ContextWorker` →
`LucasCore.prepare()` → `_build_messages()` → `should_use_vision()` →
`core.intent.classify()`), aucun code mort, aucun import cassé. `git
diff` sur `core/intent.py` depuis la pause : vide — rien n'y a changé.

### Aspect 2 — auto-imitation de refus : cause réelle trouvée et corrigée le 03/08/2026

**Reproduit en direct**, screenshot à l'appui (copie de la vraie base de
Cyril, jamais le fichier live ; vrai Ollama ; vraie capture d'écran/OCR) :
`classify()` détecte bien la question comme `ECRAN`, l'OCR lit
réellement l'écran, le bloc vision est injecté avec la consigne
explicite « Ne dis JAMAIS que tu ne peux pas voir l'écran : tu viens de
le faire. » **Le modèle (qwen2.5:7b) répond quand même qu'il n'a pas
accès à l'écran** — parce que les derniers tours d'historique
(`SOURCE_HISTORY_MESSAGES`) sont des refus identiques répétés : il
imite son propre motif d'échec récent plutôt que de suivre la consigne
qui le contredit. Aggravé par le réflexe naturel de réessayer une
question qui échoue — chaque nouvel essai renforce le motif imité.

**Correctif** (`core/lucas_core.py`) : `is_vision_refusal()`, un filtre
par mots-clés/regex qui retire de l'historique récent les réponses de
l'ASSISTANT (jamais les questions de Cyril) qui ressemblent à un refus
de vision déjà observé, uniquement quand un nouveau bloc vision va être
injecté pour le tour courant — aucun effet sur le RAG, la finance ou une
conversation ordinaire. Motifs construits à partir des formulations
RÉELLEMENT observées (pas inventées).

**⚠️ Filtre heuristique, explicitement pas une solution définitive.**
Revalidé le même jour sur l'état réel de la base de Cyril, qui avait
entre-temps accumulé 8 refus consécutifs supplémentaires (Cyril a
continué à tester pendant le correctif) : le filtre n'a reconnu qu'une
partie des formulations (le modèle paraphrase différemment à chaque
fois, il ne répète pas verbatim) — 2 refus sur 3 dans la fenêtre
d'historique ont échappé au filtre, formulés différemment des 3 motifs
connus. **Malgré cette couverture incomplète, la réponse finale a
correctement décrit l'écran réel** au lieu de refuser — première fois
que ce scénario aboutit depuis le début de ce signalement. Pas assez de
recul pour garantir que ça tienne à chaque fois ; à surveiller.

**Piste de fond, pas construite maintenant** : une fois le schéma
mémoire confiance/provenance implémenté (`IDEAS.md` #2bis), ce filtrage
pourra se faire proprement via une métadonnée posée à l'écriture
plutôt que par correspondance de texte après coup, sans dépendre des
formulations exactes que le modèle choisit d'utiliser.

Tests : `test_vision_routing.py` — historique synthétique à 3 refus
consécutifs (confirmé filtré), garde qu'un tour normal (sans nouveau
déclenchement vision) n'est jamais filtré, reconnaissance des 3
formulations réelles connues. 742/742 tests passent au total.

Distinct du point OCR/classifieur (§3, tableau Phase 3, « Vision écran »)
qui reste, lui, clos et sans lien avec ce signalement.

## 5.7 Reasoning Engine v1 — construit et testé le 03/08/2026, désactivé par défaut

Session autonome (5h, Cyril absent) — chantier explicitement autorisé
(hooks multi-agents déjà posés le même jour, IDEAS.md #59 catalogué comme
prêt). `core/reasoning_engine.py` : une seule étape déterministe, pas les
« débat interne 3 personas / arbre de décision 3D » du catalogue complet
— volontairement hors périmètre v1. `ReasoningEngine.plan(question,
context)` demande au modèle local de décomposer une question complexe en
2-4 points à couvrir, **sans jamais répondre à sa place** ; le plan est
injecté comme bloc de contexte supplémentaire dans
`LucasCore._build_messages()`, avant l'appel qui produit la vraie
réponse (celui qui a accès à la vision, au RAG, à l'historique). Pattern
explicitement pré-autorisé par CLAUDE.md règle 12 : code Python
déterministe qui enchaîne des appels LLM séquentiels, pas un agent
autonome.

**Validé en conditions réelles**, vrai Ollama (`qwen2.5:7b`) : questions
simples (« quelle heure est-il ? », « bonjour ») → aucun plan (le modèle
répond `AUCUN`, comme demandé) ; questions complexes (calcul de budget
avec plusieurs contraintes, comparaison assurance-vie/PEL) → plan court
et pertinent (2 points, jamais de réponse anticipée). 8 tests unitaires
(`test_reasoning_engine.py`, LLM mocké) + 3 tests d'intégration
(`test_router.py` : le bloc n'apparaît que si activé, jamais vers le
cloud, même garde que RAG/événements).

**`REASONING_ENGINE_ENABLED = False` (config.py), volontairement.** Un
changement de qualité de réponse sur TOUTES les questions complexes ne
se décide pas seul, sans que Cyril l'ait entendu sur de vraies
questions — même logique que `VLM_ENABLED`. Rien à activer sans son
retour ; le module existe, testé, prêt.

## 5.8 Semantic Desktop v1 — construit et testé le 03/08/2026, lecture seule

Même session autonome. `modules/semantic_desktop.py` (IDEAS.md pilier 5,
catalogue #16) : **périmètre restreint en autonomie**, décision prise
sans Cyril présent pour trancher — l'idée catalogue parle
d'« auto-organisation selon habitudes », c'est-à-dire déplacer/renommer
de vrais fichiers. Ça relève d'une action système à risque (liste
blanche + confirmation) et `core/decision_engine.py` n'existe toujours
pas (voir §3, « Hors tableau — Decision Engine »). Choix fait : ce
module reste **strictement lecture seule** — jamais un déplacement, un
renommage ou une modification de fichier sur le disque de Cyril. Pas de
nouvelle classification LLM non plus (« pas de GraphRAG complexe ») :
tout repose sur l'infrastructure RAG déjà en place
(`modules/rag_manager.py` — ChromaDB, métadonnées `source`/`periods`
déjà calculées à l'indexation).

Trois fonctions, toutes lecture seule :
- `list_documents()` — documents actuellement indexés.
- `related_documents(source_id, top_k)` — documents sémantiquement
  proches d'un document donné (interroge ChromaDB avec le premier
  morceau du document source), déduplication par document, jamais le
  document source lui-même.
- `group_by_period()` — regroupement déterministe par période déjà
  extraite (`core/dates.py`), pas une classification par sens/projet au
  sens plein de l'idée catalogue.

**Validé en conditions réelles, sur la vraie collection de Cyril**
(39 documents, lecture seule — vérifié qu'aucune écriture n'a eu lieu) :
`list_documents()` rend les 39 sources réelles ; `related_documents()`
sur une offre d'emploi Aide-soignant retrouve deux autres offres du même
métier — cohérent ; `group_by_period()` produisait 171 groupes de
périodes réels. **Point de vigilance signalé ici, corrigé le
03/08/2026** (session autonome suivante) — voir juste en dessous.

### Correctif granularité `group_by_period()` — 03/08/2026, session autonome

171 groupes pour 39 documents, diagnostiqué avant de coder quoi que ce
soit : la lecture de `modules/rag_manager.add_text()` montre que
`periods` est calculé UNE SEULE FOIS sur le document entier (pas par
morceau), donc identique sur tous les chunks d'un même document — le
bruit n'était pas là. La vraie cause est que `core/dates.extract_periods()`
ajoute TOUJOURS le mois ET l'année pour une même date trouvée
(volontaire, voir son en-tête — sert le FILTRAGE de recherche
`RAG_MAX_DISTANCE_DATED`), et `group_by_period()` utilisait les deux
comme clés de groupe séparées. Un document qui mentionne beaucoup de
vraies dates (relevé de carrière, CV listant des années d'expérience)
se retrouvait éclaté sur des dizaines de groupes mois+année
quasi redondants — `Relevé_de_Carrière2026.pdf` à lui seul contribuait
136 clés.

**Correctif** : `group_by_period()` (`modules/semantic_desktop.py`) ne
garde que les clés de période SANS tiret (niveau année). Rien d'autre ne
change — ni `core/dates.py`, ni le format d'indexation
(`rag_manager.add_text`) : la précision mois reste entière pour la
recherche datée, seul ce regroupement d'affichage change de niveau.
Mesuré sur la vraie collection après correctif : **40 groupes pour 39
documents** (un par document, plus les années partagées entre
documents), contre 171 avant.

3 tests mis à jour pour refléter le niveau année (les données de test
fournissaient directement une chaîne `periods`, ce n'était pas un test
sur la vraie invariant mois+année de `core/dates.py`) + 1 test de
non-régression explicite (`test_group_by_period_ignores_month_level_granularity`)
qui échoue si une clé contenant `-` réapparaît un jour dans le résultat.
9/9 passent ; suite complète rejouée sans régression ailleurs (aucun
autre module ne consomme `group_by_period()` à ce jour).

9 tests (`test_semantic_desktop.py`, collection ChromaDB simulée, un
ajouté par le correctif ci-dessus) dont un qui échoue si le module
importe un jour un mécanisme d'écriture fichier (`shutil.move`,
`.rename(`, `.unlink(`...) — garde-fou explicite du périmètre lecture
seule, pas juste une note dans un commentaire.

### Contrepartie mobile (PWA) — 03/08/2026, session autonome

Semantic Desktop n'avait aucune route REST : accessible uniquement en
important `modules.semantic_desktop` côté Python, invisible depuis le
pont mobile. Trois routes ajoutées à `api/server.py`, même garde de
jeton que `/history` (les noms de fichiers de Cyril sont aussi révélateurs
que l'historique de conversation) :

- `GET /documents` — `list_documents()`
- `GET /documents/periods` — `group_by_period()`, niveau année (correctif
  ci-dessus)
- `GET /documents/{source_id}/related?top_k=N` — `related_documents()`

Nouveau panneau PWA « Mes documents » (`static/js/documents.js`, icône 📁
à côté du bouton sécurité) : tiroir qui charge `/documents/periods` à
l'ouverture (une seule fois par session), années triées de la plus
récente à la plus ancienne, « sans période » toujours en dernier. Cliquer
un document interroge `/documents/{id}/related` et affiche la liste
inline, avec un état de chargement mis en cache par document (pas de
requête répétée à chaque clic).

**Reasoning Engine n'a pas de contrepartie séparée à construire** : `/chat`
et `/ws` passent tous les deux par `LucasCore.ask()` → `_build_messages()`,
donc le mobile bénéficie automatiquement du même comportement que l'UI
PySide6 dès que `REASONING_ENGINE_ENABLED` passe à `True` — rien à
brancher spécifiquement.

**Observation en conditions réelles, pas un bug de ce correctif** : le
groupe le plus récent affiché est « 2094 », suivi de « 2092 », « 2056 »...
— des années extraites du CORPS d'un vrai document (`extract_periods()`
est volontairement généreux, voir `core/dates.py`), pas de vraies dates.
`group_by_period()` fait exactement ce qui est demandé (une clé par année
détectée) ; c'est la détection elle-même qui, sur ce document précis,
trouve une séquence de chiffres qui ressemble à une année sans en être
une. Visible seulement maintenant qu'il existe un écran pour parcourir
les groupes — non traité ici : toucher `extract_periods()` sans mesure
risquerait de dérégler le filtrage RAG déjà calibré (`RAG_MAX_DISTANCE_DATED`)
pour un gain d'affichage seulement. À revisiter si Cyril trouve ça gênant
en usage réel.

**Validé en conditions réelles** : instance uvicorn jetable sur le port
8801 (jamais touché le port 8000 — voir l'incident ci-dessous), PWA
ouverte dans un vrai Chrome via `claude-in-chrome`, jeton réel de `.env`.
`/documents/periods` rend les 40 vrais groupes ; ouvrir un groupe affiche
le vrai nom de fichier ; cliquer un document interroge `/documents/{id}/related`
et affiche soit les documents proches réels, soit « Aucun document proche
trouvé » ; réouvrir/refermer un groupe fonctionne ; aucune erreur console
au chargement ni après interaction. Instance de test arrêtée après
vérification.

5 tests ajoutés (`test_server.py`, `SemanticDesktop` mocké — même
garde-fou de jeton vérifié explicitement).

**⚠️ Incident trouvé pendant cette validation, sans lien avec le code
ci-dessus** : le port 8000 (le VRAI service, celui que le téléphone de
Cyril utilise) était injoignable au moment du test — `curl /status`
passait de `200` à une connexion refusée entre deux vérifications. Deux
process `python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 ...`
tournaient en même temps, lancés à la même seconde exacte (03/08/2026
00:25:04) — l'un depuis `venv\Scripts\python.exe`, l'autre depuis
l'installation Python système. Ni l'un ni l'autre n'avait `--reload` :
mes modifications de `api/server.py` n'étaient donc pas la cause.

**Résolu le même jour, cause confirmée** (pas juste une hypothèse) :

1. `netstat -ano | findstr :8000` a montré qu'**un seul des deux PID
   tenait réellement le socket LISTENING** (le python système), avec une
   vraie connexion `ESTABLISHED` (un Chrome sur le LAN, pas le téléphone
   ce jour-là). L'autre PID (le python venv) ne tenait rien : son
   `bind()` avait échoué silencieusement au démarrage.
2. Ce PID venv a été tué, jugé sans risque puisqu'il ne servait aucune
   connexion. **Le service entier est tombé dans la foulée** — le PID
   système qui tenait le socket a disparu lui aussi, sans lien de
   parenté détectable au premier regard (process trees différents en
   apparence).
3. **Cause réelle trouvée en creusant** (`venv/pyvenv.cfg`,
   `Get-CimInstance ParentProcessId`) : `venv\Scripts\python.exe` sur
   Windows n'est **pas un vrai interpréteur** — c'est le stub
   « venvlauncher » standard de CPython (270 Ko), qui relance
   systématiquement le VRAI interpréteur de base
   (`pyvenv.cfg` → `home = ...\Python312`) **en process ENFANT**. Chaque
   lancement de `venv\Scripts\python.exe -m uvicorn ...` produit donc
   TOUJOURS deux process — le stub (parent) et l'interpréteur réel
   (enfant), celui qui ouvre effectivement le socket. Reproduit à
   l'identique en relançant proprement juste après : même arbre à deux
   process pour un seul et unique lancement.
   **Le PID « venv » tué à l'étape 2 n'était donc pas un doublon sans
   rapport : c'était le PARENT du process qui tenait le socket.** Le
   tuer en `-Force` a très probablement coupé l'enfant avec lui (handles
   hérités du parent — sortie standard, console/job). Aucune preuve de
   journal Windows disponible (l'audit de fin de process n'est pas
   activé sur cette machine), mais le mécanisme est démontré et
   cohérent avec toutes les observations — **cause confirmée**, pas
   « non confirmée ».
4. Instance relancée proprement (`venv/Scripts/python.exe -m uvicorn
   ...`), vérifiée par `netstat` (un seul PID en LISTENING) et par
   `curl /status` (200). Service restauré.

**Ce que ça change pour la suite** : ce n'était donc jamais un vrai
« double lancement » façon Ollama (deux instances indépendantes qui se
battent pour le port depuis deux origines différentes) — c'est UN SEUL
lancement qui produit structurellement deux process sur Windows à
chaque fois. La leçon Ollama (« vérifier qu'un seul process tourne »)
ne suffit donc pas ici : il faut regarder LEQUEL des deux tient le
socket avant de toucher à quoi que ce soit, et ne jamais tuer le PID
« lanceur » seul en le croyant inoffensif — voir CLAUDE.md, principe
ajouté dans « Leçons d'infrastructure ».

## 5.9 Campagne de couverture Priorité 3 (qualité/fiabilité du socle) — close le 04/08/2026

Contrairement aux passes de tests précédentes (ad hoc, module par module
suite à un bug ou un manque remarqué), celle-ci part d'une mesure réelle :
`pytest-cov` sur `core/`, `modules/`, `security/`, `api/`, `memory/`
(l'UI PySide6 est restée hors périmètre — nécessiterait une stratégie de
test Qt à part entière). Point de départ : **86 % de couverture globale**.
Point d'arrivée, après cette campagne : **96 %**.

**Discipline suivie sur chaque module**, sans exception : mocker
uniquement la frontière d'E/S externe (registre Windows, réseau, modèle
sur disque, ChromaDB/psutil/GPUtil/win32gui) — jamais la logique réelle
sous test. Pour `security/`, contrainte supplémentaire systématiquement
vérifiée : aucun test n'accorde de nouvelle capacité d'action à un
capteur — observation seule, comme le reste du paquet. Chaque module a
suivi le même cycle : tests isolés → fichier complet → suite complète en
arrière-plan → commit avec message détaillé → push, jamais groupés.

**Modules amenés de trous réels à quasi-complet, dans l'ordre** :

| Module | Avant | Après |
|---|---|---|
| `core/llm_worker.py` | aucun test | quasi complet |
| `core/local_llm.py` | 27 % | quasi complet |
| `security/persistence_watch.py` | 50 % | quasi complet |
| `modules/rag_manager.py` (`OllamaEmbeddingFunction`) | jamais testée | couverte |
| `modules/piper_engine.py` | aucun test direct | couvert |
| `core/lucas_core.py` (`ask()`/`_emit()`) | testé seulement en intégration | couvert en unitaire |
| `security/ransomware_watch.py` | résolution des dossiers non testée | 96 % |
| `security/privacy_shield.py` | `scan()` jamais testé de bout en bout | 98 % |
| `modules/vision_manager.py` | chemin par défaut + `see_and_describe()` non testés | 80 % (résiduel : garde import `ollama`) |
| `core/world_model.py` | GPU/fenêtre active jamais mockés | 100 % |
| `modules/stt_engine.py` | sélection de backend jamais testée | 98 % |
| `modules/rag_manager.py` (`RAGManager` lui-même) | **65 %** — le plus gros trou du projet | **97 %** |
| `modules/ocr_engine.py` | 75 % | **100 %** |
| `memory/index_documents.py` | 91 % | 99 % |
| `memory/memory_manager.py` (nouveau fichier de test) | 88 % | **100 %** |
| `security/status.py` | 88 % | **100 %** |

Trois modules atteignent maintenant 100 % ; `modules/rag_manager.py` —
qui contient la logique de recherche hybride par date, déjà source de
deux bugs réels corrigés — passe de 65 % à 97 %, en construisant
`RAGManager` réellement (jamais fait ailleurs : tous les autres tests du
projet le construisent via `__new__()`, court-circuitant `__init__()`).

**Ce qui reste, volontairement** : `core/cloud_llm.py` (40 %) est un
stub intentionnel confirmé (clé API cloud vide dans `.env` de Cyril),
pas un trou. Une dizaine de modules gardent un résiduel de 3 à 12 lignes
(`api/server.py`, `modules/voice_manager.py`, `security/history.py`,
`security/monitor.py`, `core/intent.py`, `modules/stt_manager.py`,
`modules/semantic_desktop.py`, `modules/calculator.py`,
`modules/finance_categorizer.py`) — rendements décroissants, pas
poursuivis ici. L'UI PySide6 (`ui/avatar_widget.py` 48 %,
`ui/chat_widget.py` 0 %, `ui/main_window.py` 65 %) reste entièrement
hors périmètre.

**Campagne close ici.** Suite complète : 859 tests, tous verts.

## 5.10 Memory Palace — socle confiance/provenance construit le 04/08/2026

Session autonome 8-10h. `IDEAS.md` #2bis (ajout 03/08/2026) demandait
d'ajouter aux tables mémoire existantes les six champs — `source`,
`date`, `confidence`, `last_validated`, `importance`, `expiration` —
plutôt qu'un nouveau système parallèle. Fait dans `memory/memory_manager.py` :
migration additive (`_migrate_add_column()`, généralisation de l'ancien
`_migrate_add_agent_id_column()`), sur `conversations` ET `system_events`.
`date`/`last_validated` rétro-remplis depuis `created_at` sur une base
existante — un message déjà en base était vrai au moment observé, seule
valeur par défaut disponible sans reconstituer un historique perdu.

`save_message()`/`save_event()` acceptent ces six champs en paramètres
**optionnels, mots-clé uniquement**, valeurs par défaut sûres
(`confidence=1.0`, `importance=0.5`, `source` selon la table) : aucun
appelant existant du projet n'a eu besoin de changer. Deux nouvelles
méthodes de lecture, `load_history_with_metadata()` et
`load_recent_events_with_metadata()` — volontairement séparées de
`load_history()`/`load_recent_events()`, dont `LucasCore._build_messages()`
et toute la suite de tests dépendent sous leur forme `(role, message)` /
`(event_type, details, created_at)` actuelle ; les changer aurait
propagé une modification non demandée dans tout le projet.

**Portée délibérément arrêtée ici** : le socle est prêt, mais rien
n'exploite encore ces valeurs. Ni le Reasoning Engine (qui reste
désactivé, `REASONING_ENGINE_ENABLED=False`, décision de Cyril — non
touchée) ni le RAG ne repondèrent quoi que ce soit dessus aujourd'hui.
C'est le chantier suivant, pas celui-ci.

**Validé** : 12 tests dans `test_memory_manager.py` (colonnes présentes,
défauts sensés côté message ET événement, surcharge explicite par
l'appelant, rétro-remplissage sur une base à l'ancien schéma, forme de
`load_history()` inchangée). **Validation en conditions réelles** : migration
exécutée sur une COPIE de la vraie base de Cyril (`memory/lucas_memory.db`,
jamais le fichier live) — 100 conversations et 233 événements présents
avant/après, premier message identique bit à bit, toutes les colonnes
créées et rétro-remplies (`date`/`last_validated` = `created_at` d'origine,
ex. `2026-08-02 20:06:58`). Suite complète du projet : 865 passed.

## 5.11 Decision Engine — mécanisme construit le 04/08/2026, AUCUNE action câblée

Session autonome 8-10h, suite du 5.10. `core/decision_engine.py`
n'existait pas (voir §3, « Hors tableau — Decision Engine »). Construit
avec un garde-fou explicite posé par l'instruction de session : construire
et tester le mécanisme, ne câbler aucune nouvelle action système réelle
dessus.

**Modèle** : trois catégories par CONSÉQUENCE, pas par nature technique —
`READ` (jamais de confirmation), `WRITE` (confirmation exigée, pas
journalisée — un volume ou une luminosité changés ne laissent pas de
trace utile), `EXECUTE` (confirmation exigée ET journalisée — un effet
externe en laisse une). `DecisionEngine.request(name, run)` n'appelle
`run` QUE si l'action est passée ; sinon lève `ActionDenied`, jamais une
valeur "refusé" retournée en silence. Sans callback `confirm` injecté :
refus systématique par défaut — même principe que `is_sensitive()`
(CLAUDE.md) qui ne consulte jamais un classifieur, un mécanisme absent ne
doit jamais avoir pour effet d'AUTORISER.

⚠️ **Écart trouvé par rapport à l'instruction de session, documenté plutôt
que corrigé en silence** : elle demandait de suivre « la liste blanche
déjà documentée (volume, luminosité, presse-papier, lancement d'appli,
capture d'écran) » — recherche faite dans `IDEAS.md`/`VISION_LONG_TERME.md`/
`ROADMAP.md`, **aucune liste catégorisée de ce type n'existe** ; le seul
mécanisme de liste blanche réel reste `modules/automation_manager.py`
(lancement d'appli uniquement, sans catégorie read/write/execute). Les
cinq exemples cités dans l'instruction ont servi de base pour
`DEFAULT_ACTIONS` — un jeu d'`ActionSpec` illustratif, catégorisé, **non
enregistré automatiquement** dans le moteur (`DecisionEngine()` démarre
toujours vide) et sans aucun callable réel derrière : aucun n'ajuste le
volume, la luminosité ou le presse-papier de la machine de Cyril.

**Ce qui n'a PAS été touché, comme demandé** : `modules/automation_manager.py`
reste exactement tel quel — lancement d'appli sans confirmation, jamais
reroutée par ce moteur. Semantic Desktop reste lecture seule. Aucune
carte d'approbation UI (`IDEAS.md` #80), aucun STOP mid-tool-call (#81) —
les deux restent gatées sur une session où Cyril valide l'UI en direct,
`confirm`/`log_event` restent de simples callables injectables en
attendant.

**Validé** : 24 tests dans `test_decision_engine.py` — lecture jamais
confirmée (avec et sans callback), écriture refusée par défaut puis
acceptée sur confirmation (jamais journalisée), exécution refusée par
défaut puis acceptée ET journalisée sur confirmation (refus aussi
journalisé), action inconnue refusée, `ActionSpec` complet transmis à
`confirm` (nom + description, pour une future carte d'approbation), les
8 `DEFAULT_ACTIONS` catégorisés comme annoncé. `run` n'est jamais appelé
quand l'action est refusée (compteur d'appels vérifié à chaque cas de
refus). Suite complète du projet : 889 passed.

## 5.12 STT desktop — câblé le 04/08/2026, PySide6 côté PC

Session autonome 8-10h, suite du 5.11. Le STT n'était câblé que côté
pont mobile (`api/server.py` → `STTEngine.transcribe_base64()`) : zéro
chemin STT dans `ui/main_window.py`, confirmé en grepant le fichier avant
de commencer (aucune occurrence de `STTEngine`/`stt_engine`/`micro`).

**Ce qui est construit** : un bouton 🎙️ dans la barre de saisie,
`STTWorker(QThread)` (même patron que `TTSWorker`/`ContextWorker` déjà
en place), et `_stt_engine = STTEngine()` en instance de module unique —
exactement le même raisonnement que `_stt_engine` dans `api/server.py`
(recharger Whisper par appel serait coûteux). **Un seul et même
`STTEngine`** pour les deux chemins (mobile et desktop) : jamais un
second pipeline de transcription, cohérent avec le principe du pont
audio unique (`VISION_LONG_TERME.md`).

⚠️ **Ce n'est PAS un bouton micro au sens propre.** Ce PC n'a pas de
microphone (`VISION_LONG_TERME.md` §2, Pilier 3 — confirmé, pas
contourné). Le bouton ouvre un sélecteur de fichier (`QFileDialog`) et
transcrit un fichier audio déjà enregistré — utile pour un mémo vocal
existant, pas pour parler en direct au PC. Le texte transcrit remplit le
champ de saisie SANS envoi automatique : Cyril garde la main pour
relire/corriger, comme pour tout ce qu'il tape.

**Validé, deux niveaux** :
- **Unitaire (rapide, 9 tests, `test_ui_workers.py`)** : `STTEngine`
  factice — transcription réussie, `STTUnavailable` rapportée
  lisiblement, toute autre exception avalée sans faire tomber le thread,
  dialogue annulé ne lance rien, texte transcrit remplit le champ sans
  déclencher `send_message()`, erreur affichée dans le chat, bouton bien
  câblé, `closeEvent` attend `stt_worker`.
- **Réel, de bout en bout (`test_integration.py`, marqueur
  "integration")** : Piper (réel) synthétise « Bonjour Luca's, ceci est
  un test de transcription. », faster-whisper (réel) la transcrit — AUCUN
  mock des deux côtés. Résultat obtenu : *« Bonjour Loucoise, ceci est un
  test de transcription. »* — Whisper déforme « Luca's » en « Loucoise »
  (artefact voix Piper + reconnaissance sur un nom propre inhabituel),
  tout le reste de la phrase est exact ; langue détectée `fr`, confiance
  0,97. L'assertion ne porte volontairement pas sur le nom (fragile),
  seulement sur « test »/« transcription » (présents).

**Reste bloqué, comme prévu** : aucune validation avec un vrai micro —
ce PC n'en a pas, ça attend le pont mobile / un speakerphone.

Suite complète du projet : 898 passed (889 + 9 unitaires ; le test
d'intégration synthétique est le 9e test marqué "integration", exclu du
compte par défaut).

## 5.13 Modes AURA — MVP réduit (Working + Deep Focus), détection seule, 04/08/2026

Session autonome 8-10h, suite du 5.12 — dernière priorité de la liste,
traitée dans le temps restant. `IDEAS.md` §3 catalogue 8 modes ; MVP
volontairement réduit à 2, les moins ambigus à détecter sans LLM.

**`core/aura_modes.py`** : `AuraModeEngine`, déterministe (comme
`core/router.py` — du code Python qui décide, jamais un LLM, CLAUDE.md
règle 12). `detect(active_window)` reconnaît Working par une liste de
marqueurs d'app dans le titre de fenêtre (`core/world_model.py`,
`get_snapshot()["active_window"]`) — VS Code, PyCharm, Excel, Word,
PowerPoint, Outlook, terminal/PowerShell, Notepad++. Deep Focus, lui,
n'est **jamais déduit d'une fenêtre** — seulement d'une commande
explicite (`handle_command()`) : bloquer les notifications sur une
inférence fragile serait pire que ne rien bloquer. Une fois activé,
Deep Focus reste actif quelle que soit la fenêtre ensuite au premier
plan, jusqu'à désactivation explicite — le seul mode "collant" des deux.

⚠️ **Bug réel trouvé en testant, pas en relisant** : la phrase de
désactivation « désactive le mode focus » contient littéralement la
sous-chaîne « active le mode focus » — sans vérifier d'abord les phrases
de désactivation, une commande pour ARRÊTER le mode l'aurait activé. Le
test `test_an_explicit_command_deactivates_deep_focus` l'a immédiatement
fait échouer ; corrigé en vérifiant OFF avant ON dans `handle_command()`.

**Portée délibérément arrêtée à la détection** — comme `core/decision_engine.py`
(§5.11) : les "comportements" de la table `IDEAS.md` (notifications
filtrées, musique lo-fi, compte à rebours, raccourcis pro...) sont de
vraies actions système qui n'existent pas encore dans le projet. Les
construire dépasse un MVP et empièterait sur ce que Decision Engine est
censé arbitrer une fois réellement câblé — non fait ici, à dessein.

**Les 6 autres modes** (Creating, Meeting, Gaming, Entertainment,
Learning, Social) restent catalogués dans `IDEAS.md`, prêts à suivre le
même patron (liste de déclencheurs -> `AuraMode`), mais ne sont pas
construits : chacun mérite sa propre liste d'apps/mots-clés vérifiée
avec Cyril, pas une extrapolation en session autonome.

**Validé** : 15 tests dans `test_aura_modes.py` (Working sur plusieurs
apps réelles, insensible à la casse, jamais déduit pour Deep Focus,
Deep Focus collant à travers un changement de fenêtre, activation ET
désactivation explicites, phrase neutre sans effet). **Validation en
conditions réelles** : moteur exécuté contre le VRAI `get_snapshot()` de
cette machine, maintenant — fenêtre active réelle `"Claude"`, mode
détecté `NONE` (correct, pas dans la liste des apps pro) ; après la
commande réelle « active le mode focus », mode `DEEP_FOCUS`, reste actif
sur la même fenêtre. Suite complète du projet : 913 passed.

## 5.14 Memory Palace — première exploitation réelle de confiance/provenance, 04/08/2026

Session autonome, suite directe de la nuit du 03-04/08 (§5.10 posait le
socle, non exploité). `core/memory_weighting.py` (nouveau) :
`annotate_uncertain_history()` / `annotate_uncertain_events()`.

**Portée, posée en tête du module** : un message envoyé à un LLM n'a pas
de poids numérique réglable — la seule façon réelle de le faire "peser
moins" est de le DIRE au modèle. `UNCERTAIN_MARKER` est préfixé au
contenu d'un souvenir dont `confidence < MEMORY_CONFIDENCE_THRESHOLD`
(0.6, `config.py` — même ordre de grandeur que `TranscriptResult.is_confident`,
`modules/stt_engine.py`) ou dont `expiration` est passée. Une date
d'expiration illisible n'est JAMAIS traitée comme expirée — même
principe que `security/status.py::_is_active()`.

**Branché** : `core/lucas_core.py::_build_messages()`, à la toute
première étape — `history = annotate_uncertain_history(self.memory.load_history_with_metadata())`
remplace l'ancien `self.memory.load_history()`, et le même geste pour
les événements système. Choix délibéré : les DEUX fonctions rendent
EXACTEMENT la même forme de tuples que les méthodes qu'elles
remplacent — tout le reste de `_build_messages()` (troncatures
`SOURCE_HISTORY_MESSAGES`/`CLOUD_HISTORY_MESSAGES`, filtre
`is_vision_refusal()`, `fit_history_to_budget()`) continue d'opérer sur
des tuples ordinaires, strictement inchangé. Cette prudence n'était pas
optionnelle : `_build_messages()` porte plusieurs correctifs mesurés en
conditions réelles (0/9 → 9/9 sur des sondes précises, voir §5.5/§5.6) —
le risque de régression y est plus élevé que partout ailleurs dans le
projet.

**PAS branché** sur le RAG (`modules/rag_manager.py`) : les documents
RAG vivent dans ChromaDB avec un schéma de métadonnées différent
(source, chunk, sha, periods) qui n'a jamais eu de colonne
confidence/expiration — IDEAS.md #2bis parlait explicitement de "la
table memories/events SQLite existante", pas de ChromaDB. Étendre le
RAG serait un chantier différent, non demandé ici. **PAS branché** sur
Reasoning Engine — `REASONING_ENGINE_ENABLED` reste `False`, non touché.

⚠️ **Effet secondaire découvert en réparant les tests, pas en codant** :
brancher `load_history_with_metadata()`/`load_recent_events_with_metadata()`
dans `_build_messages()` a cassé 66 tests dans 6 fichiers
(`test_lucas_core.py`, `test_memory_context.py`, `test_history_budget.py`,
`test_vision_routing.py`, `test_router.py`, `test_dates.py`) — chacun
définit sa propre fausse mémoire (`_FakeMemory`/`_Memoire`) qui
n'implémentait que `load_history()`/`load_recent_events()`. Les 6
classes ont reçu les deux méthodes enrichies manquantes (dérivées de
leurs méthodes existantes, confiance 1.0 par défaut — aucun changement
de comportement testé). Résolu avant de continuer, pas laissé de côté.

**Pourquoi c'est un no-op aujourd'hui, et c'est le résultat attendu** :
aucun appelant du projet n'écrit une confiance réduite ou une
expiration. **Validé sur une copie de la vraie base de Cyril** :
100 messages, une seule valeur de confiance trouvée (`1.0`), aucune
expiration — `annotate_uncertain_history()`/`annotate_uncertain_events()`
rendent des résultats identiques bit à bit à `load_history()`/
`load_recent_events()`. Le socle est prêt pour le jour où une source
moins fiable écrira avec une confiance réduite ; rien ne le fait encore.

**Validé** : 13 tests dans `test_memory_weighting.py` (message/événement
pleinement fiable inchangé, seuil configurable et comparaison stricte,
expiration passée/future/absente/illisible, event_type jamais touché
— `format_events_for_prompt()` en dépend pour filtrer `tts_*` —, et un
test bout en bout vérifiant qu'un souvenir à faible confiance atteint
bien le prompt signalé). Suite complète : 926 passed.

## 5.15 Decision Engine — la liste blanche formalisée reflète l'existant, 04/08/2026

Session autonome, correction de l'écart trouvé et documenté la nuit
précédente (§5.11) : aucune liste blanche catégorisée n'existait avant
`core/decision_engine.py`, contrairement à ce qu'une instruction de
session supposait. `DEFAULT_ACTIONS` mélangeait cinq exemples
illustratifs (volume, luminosité, presse-papier, lancement d'appli,
capture d'écran) sans étiquette distinguant le réel de l'aspirationnel.

**Séparé en deux, sans rien câbler de nouveau** :
- `automation_manager_actions()` — **réel**. Fonction (pas une
  constante figée) qui lit `modules.automation_manager.WHITELISTED_APPS`
  à CHAQUE APPEL et génère un `ActionSpec(EXECUTE)` par application
  (`launch_chrome`, `launch_calculatrice`, `launch_notepad`,
  `launch_explorer` aujourd'hui). Générée plutôt que recopiée à la main :
  une copie figée aurait dérivé au premier ajout/retrait d'application —
  exactement le problème corrigé ici. Testé : elle suit un changement de
  `WHITELISTED_APPS` sans toucher au fichier de test
  (`test_automation_manager_actions_cannot_silently_drift`).
- `ILLUSTRATIVE_ACTIONS` — **aspirationnel**, renommé depuis
  `DEFAULT_ACTIONS`, `launch_app` (générique) retiré car redondant avec
  les actions réelles désormais nommées précisément. Reste volume,
  luminosité, presse-papier, capture d'écran — aucun callable réel,
  sert d'exemple pour un futur chantier OS Controller (S6).

**Rien de nouveau câblé** : ni l'une ni l'autre n'est enregistrée
automatiquement dans un `DecisionEngine` en cours d'exécution.
`modules/automation_manager.py` n'a pas été modifié — toujours aucune
confirmation avant de lancer une application, exactement comme avant ce
commit. Documenté dans `CLAUDE.md` (nouvelle précision, section
« Liberté conditionnée à la protection ») pour que la distinction
réel/aspirationnel reste visible sans relire ce fichier.

**Validé** : `test_decision_engine.py` passe de 24 à 27 tests (un cas
`launch_app` retiré du paramétrage illustratif, 4 tests ajoutés pour
`automation_manager_actions()` — dérivation correcte, catégorie EXECUTE,
non-enregistrement automatique, résistance à la dérive). Suite
complète : 929 passed.

## 5.16 Fermeture des trous de couverture résiduels, 04/08/2026

Session autonome, Priorité 3. Les ~10 modules à 3-12 lignes non
couvertes identifiés la veille (§5.9) : `core/intent.py`,
`modules/stt_manager.py`, `modules/semantic_desktop.py`,
`security/history.py`, `security/monitor.py`,
`modules/finance_categorizer.py`, `modules/voice_manager.py`,
`api/server.py`. `modules/calculator.py` écarté sans y toucher — son
seul residu est le bloc `__main__`, même catégorie acceptée partout
ailleurs dans le projet.

Rien d'exceptionnel module par module — des branches jamais exercées
par manque d'un scénario précis (échec réseau, cache plein, fichier
corrompu, message WebSocket inconnu), toutes fermées en suivant les
patrons déjà établis (mock de la frontière d'E/S, jamais de la logique).
Un vrai bug trouvé au passage :

⚠️ **`core/intent.py::classify()`** — en isolant le test du nettoyage de
cache sur la branche héritée (`_CACHE.clear()` ligne 329), l'appel
récursif interne (`classify(precedente, "", _inherit=False)`) s'est
révélé être celui qui viderait le cache EN PREMIER si la question
précédente n'est pas déjà en cache — la branche héritée elle-même ne
voit alors jamais un cache plein. Pas un bug de production (le
comportement observable — un cache qui ne dépasse jamais `_CACHE_MAX` —
reste correct dans tous les cas), mais un premier test qui vérifiait la
bonne PROPRIÉTÉ sans exercer la bonne LIGNE. Corrigé en pré-remplissant
la question précédente dans le cache pour isoler proprement la branche
héritée.

**`api/server.py`** — les deux boucles de fond WebSocket
(`_push_system_state`, `_push_security_status`, jamais appelées dans
aucun test) tournent en `while True` : testées en appelant directement
la coroutine avec un faux WebSocket dont `send_json()` lève — la boucle
s'arrête au premier tour sans jamais avoir besoin d'un vrai
`asyncio.sleep()`.

**Détail par fichier** (tests ajoutés) : `core/intent.py` +4 (contexte
vide après filtrage, `_ask_classifier` sur Ollama injoignable, cache
plein sur classification directe ET héritée) ; `modules/stt_manager.py`
+4 (`is_available()` vrai/faux, chemin mobile qui échoue) ;
`modules/semantic_desktop.py` +4 (sans ChromaDB pour les deux méthodes,
entrée sans `source`) ; `security/history.py` +4 (JSON valide mais pas
un objet, échec d'écriture, compte à rebours d'apprentissage) ;
`security/monitor.py` +3 (`scan_runtime()`/`scan_all()` jamais appelés,
échec de sauvegarde d'état) ; `modules/finance_categorizer.py` +2
(`ask_local` réellement appelé par défaut, repli LLM réellement atteint
pour un libellé non reconnu) ; `modules/voice_manager.py` +4 (log sans
callback, forward vers Piper, échec de libération audio, liste des
voix) ; `api/server.py` +6 (dépendance manquante sur `/system`, type de
message WebSocket inconnu, échec du classifieur vision, les deux
boucles de fond).

Suite complète : 957 passed (929 + 28 nouveaux tests). Couverture
globale (`core`/`modules`/`security`/`api`/`memory`) : 96% → 98%.
Résiduel accepté, même catégorie que partout ailleurs (stub
`cloud_llm.py`, blocs `__main__`, imports de compatibilité, UI PySide6
hors périmètre) : `core/cloud_llm.py` (stub confirmé), une poignée de
lignes à 1-8 par fichier sur `core/dates.py`, `core/lucas_core.py`,
`modules/calculator.py`, `modules/finance_manager.py`,
`modules/rag_manager.py`, `modules/vision_manager.py` (garde d'import
`ollama`), `modules/weather_manager.py`, `modules/web_search.py`,
`security/guardian.py`, `security/ransomware_watch.py`.

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
