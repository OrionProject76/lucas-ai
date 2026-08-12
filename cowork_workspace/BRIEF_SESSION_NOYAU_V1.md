# BRIEF DE SESSION — NOYAU LUCA'S V1
**Pour : Claude Code | Rédigé par : Claude (Lead Architect) avec Cyril | Date : 08/08/2026**

---

## 1. Objectif de la session

Construire le **noyau minimal utilisable au quotidien** de Luca's. Quatre briques, pas une de plus. Tout ce qui n'est pas listé en §3 est **hors périmètre** — si une idée d'amélioration hors périmètre émerge, la déposer dans `cowork_workspace/requests/` au lieu de l'implémenter.

Principes de travail (hérités des règles Karpathy déjà installées + CLAUDE.md) :
- Réfléchir avant de coder : poser les hypothèses en début de session.
- Simplicité d'abord : le minimum qui remplit les critères de validation.
- Changements chirurgicaux : ne pas toucher aux modules fonctionnels existants (chat, TTS, PWA, WebSocket bridge) sauf nécessité documentée.
- Exécution par objectif : chaque brique a ses critères de validation (§4) — boucler jusqu'à ce qu'ils passent, pas au-delà.

---

## 2. Décision d'architecture nouvelle : ROUTAGE HYBRIDE LOCAL/CLOUD

**Décision actée par Cyril le 08/08/2026.** Luca's devient hybride :

| Trafic | Destination | Exemples |
|---|---|---|
| Données sensibles, fichiers locaux, contrôle PC, mémoire | **Local uniquement** (qwen3:14b / gpt-oss:20b via Ollama) | Organisation de dossiers, lecture de documents personnels, finance, tout ce qui contient chemin de fichier, contenu d'écran ou donnée personnelle |
| Conversation générale, humour, raisonnement complexe, mode vocal | **Cloud (API Anthropic)** après filtrage | Discussion libre, brainstorming, explications, personnalité "JARVIS" |

### Règles impératives du routeur
1. **Local par défaut.** Le cloud est une escalade explicite, jamais le chemin par défaut.
2. **Filtrage avant envoi cloud** : réutiliser le mécanisme de détection de données sensibles existant (IBAN via catégories Unicode, etc.). Si détection positive → traitement local forcé, jamais de "nettoyage puis envoi".
3. **Plafond de coût mensuel configurable** dans `config.json` (`cloud_budget_eur`, défaut : **10 €/mois**). Compteur de tokens persistant en SQLite. À 80 % du plafond : avertissement à Cyril. À 100 % : bascule automatique en local-only jusqu'au mois suivant — pas de dépassement silencieux, jamais.
4. **Affichage de l'origine** : chaque réponse indique discrètement sa provenance (local/cloud) dans l'UI, pour que Cyril garde une vision claire de ce qui sort.
5. La clé API est stockée chiffrée (AES-256, mécanisme existant), jamais en clair dans le code ni les logs.
6. L'indicateur d'état de l'avatar (« réfléchit » / « réfléchit plus ») s'étend : « réfléchit plus » couvre désormais aussi l'escalade cloud.

---

## 3. Périmètre — les 4 briques du noyau

### Brique 1 — Chat consolidé (existant, à stabiliser)
- Conserver le chat fonctionnel actuel (streaming par blocs de phrases, historique SQLite).
- Intégrer le routeur hybride (§2) comme seule modification.
- Aucune refonte UI.

### Brique 2 — OS Controller sous liste blanche
- Module `core/os_controller.py` : actions système via **liste blanche stricte** de fonctions codées à la main (pas de scripts générés par LLM — règle CLAUDE.md non négociable).
- Actions v1 : ouvrir application (chemin whitelisté), organiser fichiers (déplacer/renommer dans dossiers autorisés), captures d'écran, volume, presse-papiers.
- Garde-fous obligatoires dès le premier commit :
  - `allowed_directories` dans `config.json` (défaut : dossiers utilisateur uniquement, jamais `C:\Windows` ni `Program Files`)
  - `confirm_destructive: true` — toute suppression/écrasement demande confirmation UI explicite
  - Journal d'audit SQLite : chaque action exécutée est loggée (timestamp, action, paramètres, résultat)
- Pilotage via l'arbre d'accessibilité Windows (pywinauto/UI Automation) plutôt que vision d'écran — plus fiable, zéro VRAM.

### Brique 3 — Mémoire enrichie (5 niveaux)
- Étendre le schéma SQLite existant avec les métadonnées actées : **confiance, provenance, date, expiration**.
- Les 5 types : épisodique, sémantique, procédurale, émotionnelle, prospective (cf. IDEAS.md §2).
- API interne simple : `remember()`, `recall()`, `forget()` — utilisée par le chat et l'OS Controller.
- Migration des données mémoire existantes sans perte (script de migration + backup avant).

### Brique 4 — Avatar fantôme minimal
- Évolution du composant **QPainter v2 existant** — pas de nouveau composant, pas de Godot.
- Yeux + bouche animés uniquement. États : écoute / regarde / observe / parle / réfléchit / réfléchit plus.
- Irrégularité organique (clignements non périodiques, micro-variations) — cf. principe "vivant, pas robotique" (VISION_LONG_TERME.md addendum 02/08).
- Budget ressources : < 2 % CPU, 0 VRAM dédiée.

---

## 4. Critères de validation (fin de session = tout coché)

| # | Critère | Méthode de vérification |
|---|---|---|
| V1 | Une conversation vocale/texte fluide passe par le cloud et une demande contenant un chemin de fichier reste en local | Test manuel avec logs de routage visibles |
| V2 | Une chaîne contenant un IBAN (avec espaces insécables) n'est jamais envoyée au cloud | Test unitaire avec les cas de typographie française déjà documentés |
| V3 | Le compteur de coût s'incrémente et la bascule à 100 % du plafond fonctionne | Test avec plafond artificiellement bas (0,01 €) |
| V4 | `os_controller` refuse une action hors liste blanche et hors `allowed_directories` | Tests unitaires (action inconnue, chemin `C:\Windows`) |
| V5 | Une suppression de fichier déclenche la confirmation UI et apparaît dans le journal d'audit | Test manuel |
| V6 | `remember()`/`recall()` persistent entre deux redémarrages avec métadonnées complètes | Test automatisé |
| V7 | L'avatar affiche les 6 états et reste < 2 % CPU en idle | Observation + moniteur ressources |
| V8 | Les modules existants (TTS, PWA, WebSocket) fonctionnent toujours à l'identique | Test de non-régression manuel |

---

## 5. Exclusions explicites de cette session

**Ne pas construire, même si tentant :**
- ❌ Vision modale (modes capture d'écran/document) — session ultérieure
- ❌ STT / mode vocal continu — session ultérieure (le routage cloud prépare le terrain, c'est tout)
- ❌ Modes AURA, proactivité, multi-agents/HERMES (règle 12 — design supervisé requis)
- ❌ Détection automatique de complexité pour le routage (Phase 2 — données d'usage requises d'abord)
- ❌ Toute modification de la PWA au-delà de la non-régression
- ❌ Godot, GDExtension, interface 3D (scope abandonné — décision Cyril)
- ❌ Nouveaux modèles Ollama (qwen2.5vl:7b en attente de décision supervisée séparée)

---

## 6. Contraintes techniques rappelées

- VRAM réelle disponible : ~13 100 MB (Edge/Orange TV permanent). qwen3:14b par défaut (~9 486 MB), gpt-oss:20b en escalade locale (~12 549 MB, marges fines).
- Fichiers Python courts et modulaires (< 200 lignes quand possible).
- PySide6 uniquement. Pas de PyQt6.
- Commit Git après chaque brique validée + `SESSION_LOG.md` en fin de session.
- Mettre à jour `ROADMAP.md` (briques validées) et déposer toute idée nouvelle dans `IDEAS.md` via le flux habituel.

---

## 7. Ordre d'exécution recommandé

1. Brique 3 (mémoire) — fondation, les autres s'appuient dessus
2. Brique 2 (OS Controller) — valeur quotidienne immédiate
3. Brique 1 (routeur hybride) — nécessite la mémoire pour le compteur de coût
4. Brique 4 (avatar) — indépendante, en dernier

*Fin du brief. Toute ambiguïté rencontrée en session : déposer une note dans `cowork_workspace/requests/` plutôt que d'interpréter.*
