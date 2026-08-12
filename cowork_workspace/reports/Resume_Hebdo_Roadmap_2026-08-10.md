# Résumé hebdomadaire — ROADMAP.md
**Date de rédaction : 10/08/2026** — Source : `C:\OrionAI\ROADMAP.md` (lecture seule, jamais modifié)

⚠️ **Premier résumé hebdo de ce type.** Aucun résumé précédent trouvé dans `cowork_workspace\reports\` — la fenêtre couverte ci-dessous est donc les 7-8 derniers jours (03/08 → 10/08/2026), pas "depuis le dernier résumé".

---

## Priorité actuelle

Le tableau des Phases 0-5 (§3, en tête de fichier) n'a pas été remis à jour explicitement depuis le 03/08 — il ne reflète plus l'activité réelle. Depuis le 08/08, le travail réel se concentre sur deux fronts parallèles, hors de ce découpage :

1. **Godot / avatar 3D** — débloqué (fenêtre en coin, watchdog VRAM, pont WebSocket testés le 06-07/08) puis mis en pause au profit du chantier ci-dessous. Le mesh/shader/HUD définitifs restent le prochain jalon Godot.
2. **Chantier "noyau minimal" puis Workspace** (le vrai centre de gravité de la semaine, 08→10/08) : 4 briques de base (mémoire à 5 types, OS Controller, routeur cloud Anthropic, avatar 7 états), suivies d'une série de briefs enchaînés — Workspace PC, zone sandbox, détecteur d'économies, accueil mobile, "Bureau de l'IA", mode conversation mains libres. Chaque brief a été corrigé sur retour d'usage réel le jour même ou le lendemain.

Deux briques du noyau minimal existent mais **n'ont aucun déclencheur dans le chat** (`core/os_controller.py`, `remember()`/`recall()`) — câbler ces déclencheurs est la suite logique non encore planifiée.

La tâche planifiée `LucasVeilleModeles` (veille LLM+VLM conjointe, règle 12 de `CLAUDE.md`) était programmée pour aujourd'hui 10/08 à 09:00.

---

## Ce qui a avancé cette semaine (03/08 → 10/08/2026)

### 03-04/08 — Finance, Decision Engine, premiers tests mobiles réels
- Finance CSV : 1er relevé bancaire réel de Cyril incompatible (décision demandée, non tranchée à l'époque) ; format comptable ensuite exploité (2 bugs d'encodage/délimiteur corrigés) ; PDF évalué et écarté (trop fragile).
- Premier câblage réel du Decision Engine — lancement d'appli, sans confirmation UI (accord explicite de Cyril, temporaire).
- Premier test audio mobile réel : TTS tronqué et bouton mute corrigés ; micro incomplet identifié mais non prouvé à 100 %.
- Audit finance/RAG/TTS/vision (session 8h) : 2 bugs UI PySide6 + 1 bug AURA (faux positifs sur titres de fenêtre) corrigés.

### 05/08 — Sécurité, bascule de modèle, infrastructure
- Démarrage auto du serveur au boot Windows.
- 🔴 **Jeton d'API en clair dans les logs** — trouvé et corrigé.
- 🔴 **Luca's confirmait une action jamais exécutée** ("Bloc-notes ouvert" — faux) — corrigé, + 4 autres correctifs client.
- 🔴 **Incident grave** : des mesures de Claude Code ont détruit ~56 messages réels de l'historique de Cyril (isolation de base cassée) — sauvegardés, mécanisme corrigé.
- 8 modes AURA détectés ; confiance/provenance étendue au RAG.
- 🔴 Ollama servait depuis un magasin imbriqué (2 modèles visibles sur 14, RAG/vision cassés).
- Tutoiement durci partout ; couverture de test corrigée à 97,2 % (une section antérieure disait le contraire à tort).
- Comparatif de 5 modèles LLM → recommandation `gpt-oss:20b`, **bascule faite en production** le jour même, avec un 4e problème trouvé et corrigé (double rechargement du classifieur d'intention).
- 🔴 **Faille de sécurité** : la typographie du nouveau modèle (espaces insécables) contournait la détection de contenu sensible — corrigé.
- 🔴 **Seconde fuite du même type** trouvée dans le filtre anti-fuite de la recherche web (IBAN/carte contournables) — corrigé.
- 🔴 Routage cloud cassé (stub) envoyait les meilleures questions dans un mur — corrigé.
- Tailscale opérationnel, CORS resserré ; coexistence Tailscale/VPN Bitdefender confirmée (mécanisme initialement mal compris, corrigé).
- Cause réelle du magasin Ollama amputé trouvée et fermée (le CLI réveillait l'appli tray) ; orphelins `llama-server.exe` retenant de la VRAM nettoyés.
- Comparatif fluidité/VRAM Godot vs LLM : conclusion inversée, pas de changement de modèle nécessaire (coût réel de Godot : 246 Mo, pas les Go supposés).
- Mécanisme de veille modèles hebdomadaire créé ; tableau des modèles de `CLAUDE.md` corrigé (4 modèles fantômes retirés).

### 06/08 — Qualité de fond
- `config.json` : confirmé inerte, lu par aucun module.
- Chantier ruff (105→0 alertes) : 🔴 bug de sécurité réel trouvé au passage — le panneau sécurité comparait des dates dans deux formats différents, la fenêtre "24h" ne comptait jamais rien (PWA affichait "aucun signal" à tort) — corrigé.
- mypy réparé à 0 erreur sur 110 fichiers ; `just lint`/`just test`/`just mypy` ne fonctionnaient en réalité jamais (mauvais interpréteur Python) — corrigé.
- Couverture de test du projet portée à 100 %, puis validée par mutation (99,5 %, 602/603).
- Revalidation générale pré-Godot (12 points) : 2 écarts non-régressifs trouvés (daemon sécurité pas installé en tâche persistante ; `ruff format` jamais appliqué).
- Début session Godot supervisée : le pari du 02/08 sur le rendu s'est révélé faux (comportement en réalité binaire) — corrigé en commentaire.

### 06-07/08 — Godot
- Fenêtre en coin adoptée. 🔴 Incident sécurité : la fenêtre Godot passait par-dessus le Gestionnaire des tâches (TOPMOST) — corrigé.
- Watchdog VRAM et pont WebSocket Godot↔FastAPI testés de bout en bout (TLS, jeton).
- Direction de routage hybride actée (qwen3:14b par défaut, gpt-oss:20b à la demande) — **rien implémenté encore**, conception détaillée différée.

### 08/08 — Noyau minimal (4 briques)
- Brique mémoire (table 5 types) : incident — la vraie base de Cyril recevait des écritures de test (même piège de paramètre figé que le 05/08, retombé dedans 3 fois) — corrigé, données vérifiées intactes.
- OS Controller construit (fichiers, volume, presse-papiers, capture) — **pas câblé au chat**.
- Routeur cloud Anthropic réellement implémenté (remplace un stub) — **non vérifié en conditions réelles**, pas de clé Anthropic disponible.
- Avatar 7 états construit ; budget CPU au-dessus de la cible (2,6-2,8 % vs <2 %), non corrigé.
- Workspace E-1 (tableau de bord PC) livré ; 2 bugs remontés par Cyril (Service Worker pas rafraîchi) — corrigés.
- Refonte visuelle glassmorphism/néon cyan, contraste WCAG vérifié.

### 09/08 — Série de briefs Workspace
- Style "Terminal pro" + cartes modulaires ; bug de clic fantôme en fin de glisser — corrigé.
- Zone sandbox (isolation logicielle réseau/fichiers/process) testée en sous-processus réel, limites documentées honnêtement.
- Détecteur d'économies : 2 bugs réels sur données réelles (retraits DAB mal classés, doublons SOGECAP confondus, le second trouvé par Cyril lui-même) — corrigés.
- Accueil mobile (F-1) : 2 bugs (popover sécurité, cache Service Worker périmé) — corrigés.
- Compaction Workspace PC (0 débordement à 1280×720).
- "Poste de Commandement IA" renommé "Bureau de l'IA" ; trouvaille : OS Controller et Watchdog VRAM ne sont PAS "actifs" comme le brief le supposait.
- Mode conversation mains libres (VAD réel) : bug de course entre états "idle" serveur / "écoute" client — corrigé.

### 10/08 — Aujourd'hui
- Bug confirmé : clic fantôme du Workspace mobile avalait le tap suivant — corrigé (seuil de déplacement 6 px).
- 3 ajustements mode conversation (seuil micro, volume, commande vocale "stop" remplace le minuteur).
- Style oral pour réponses parlées : `speak` n'était threadé nulle part — corrigé.
- `ministral-3:8b` écarté de la veille modèles (hallucinations 3/3 sur le prompt réel, même défaut sur `qwen3:14b`).
- Bug réel dans la commande du daemon sécurité (pas de répertoire de travail défini) — corrigé, tâche planifiée fonctionnelle vérifiée.
- Accueil mobile enrichi de 3 compteurs réels, sans nouvelle route.

---

## Points bloqués / non résolus

- **Godot — fermetures/gels spontanés** : pas formellement fermé. ~55 min sans incident constituent un indice en faveur de la piste "c'était l'éditeur", pas une preuve. La piste de contention GPU reste testée mais non éliminée.
- **Jeton d'appairage dans l'historique du navigateur** (§5.33) : toujours ouvert, aucune décision retrouvée depuis.
- **Tailscale/Bitdefender — `UDP: false`** : coexistence confirmée fonctionnelle, mais la cause exacte du symptôme réseau reste non établie.
- **`ruff format` jamais appliqué** (95 fichiers, 54→320 alertes potentielles) — arbitrage toujours en attente.
- **Routeur cloud Anthropic (V1)** : non vérifié en conditions réelles, faute de clé API.
- **Confirmation destructive de l'OS Controller (V5)** : jamais cliquée réellement par Cyril.
- **Budget CPU de l'avatar 7 états** : au-dessus de la cible (2,6-2,8 % vs <2 %).
- **Impact batterie du mode conversation mains libres** : non mesuré.
- **Refus de saluer** signalé le 06/08 ("dis juste bonjour" → refus étrange) : non diagnostiqué.

---

## Décisions explicitement en attente de Cyril

- **Jeton d'appairage** (§5.33) : Option A (code d'appairage à usage unique), B (saisie manuelle), ou C (ne rien changer + effacer l'historique).
- **`ruff format`** : élargir le périmètre lint ou non.
- **Magasin Ollama imbriqué résiduel** (~26,7 Go) : suppression en attente de confirmation qu'il ne contient rien d'unique.
- **`config.json`** : le supprimer ou le brancher réellement.
- **Phase 2 du routage hybride** (détection automatique de complexité) : différée, "à reprendre quand l'usage réel de la Phase 1 aura montré la fréquence de bascule" — pas urgent, mais explicitement en attente.
- **Choix du VLM définitif** : différé à l'ouverture du chantier vision.
- **Rotation du jeton API** : à faire par Cyril, rien n'indique que c'est fait.

---

## Prochain jalon

Aucun jalon formel n'est explicitement rouvert dans le tableau des Phases. Les deux suites logiques les plus concrètes, visibles dans le journal, sont :
1. Câbler les déclencheurs chat manquants pour l'OS Controller et `remember()`/`recall()` — construits, jamais reliés.
2. Reprendre le chantier Godot (mesh/shader/HUD définitifs) une fois la piste "gel spontané" tranchée.

Rien de tout cela n'est planifié à une date précise dans le fichier.
