# BRIEF DE SESSION — WORKSPACE LUCA'S (E-1 uniquement)
**Pour : Claude Code | Rédigé par : Claude (Lead Architect) avec Cyril | Date : 08/08/2026**

---

## 1. Contexte

Le noyau v1 (mémoire, OS Controller, routeur hybride, avatar) est livré et stable. Une longue session d'idéation a produit `cowork_workspace/SYNTHESE_IDEES_2026-08-08.md` — un catalogue de ~30 modules futurs. **Ce brief ne porte que sur UN SEUL module de ce catalogue : la section E-1.** Lire E-1 dans le document pour le détail, mais ne rien construire d'autre de ce fichier cette session — c'est un catalogue de référence, pas une liste de tâches à exécuter d'un bloc.

## 2. Objectif de la session

Construire le **Workspace Luca's** : un tableau de bord PC qui rend visible ce que Luca's fait déjà — rapports produits, demandes en attente de validation, tâches, objectifs en cours. Extension de `cowork_workspace/`, pas une refonte.

## 3. Périmètre

- Nouvelle vue dans la PWA existante (ou route dédiée), consultée depuis le PC.
- Sources de données à afficher, **réelles, pas simulées** :
  - Rapports : fichiers dans `cowork_workspace/reports/`
  - Demandes en attente : fichiers `cowork_workspace/requests/` sans suffixe `_DONE`
  - Tâches / actions : table `action_log` (Brique 2)
  - Objectifs en cours + avancement : table `memories`, `memory_type='prospective'` (Brique 3)
- Structure en sections/blocs réorganisables **par Cyril** — pas d'auto-remodelage autonome de l'interface (voir E-1 dans la synthèse).
- **Direction esthétique, non négociable** : épuré, moderne, fonctionnel, intuitif. Identité visuelle propre à Luca's et Cyril — pas un thème générique/template importé tel quel. Cohérent avec le reste du projet (dark theme déjà en place côté chat).
- **Zéro VRAM, zéro rendu 3D.** HTML/CSS/JS léger, cohérent avec l'infra FastAPI existante.

## 4. Exclusions explicites de cette session

- ❌ E-2 (volet dataviz Chart.js/Plotly) — session dédiée ultérieure
- ❌ E-3 (zone d'exécution sandbox) — session dédiée ultérieure
- ❌ F-1 (refonte PWA smartphone style JARVIS) — session dédiée ultérieure, différent appareil/objectif
- ❌ Tout autre module de `SYNTHESE_IDEES_2026-08-08.md` (finance, domotique, mail, sécurité, etc.)

## 5. Méthode

Comme pour le noyau : explorer l'état réel du code avant de proposer un plan (structure PWA actuelle, schéma `action_log`/`memories`, routes API existantes) plutôt que de supposer. Mode plan avant exécution si le brief laisse des choix d'implémentation ouverts.

## 6. Critères de validation

- Le Workspace affiche les rapports/demandes réellement présents dans `cowork_workspace/` au moment du test.
- Tâches et objectifs affichés reflètent l'état réel des tables SQLite (pas de données figées en dur).
- Aucune régression sur chat, TTS, avatar, PWA mobile existants.
- Consultable dans un navigateur standard, aucune dépendance GPU.

## 7. Note de méthode

Commit + tests verts, `ROADMAP.md` à jour, `SESSION_LOG.md` en fin de session — même discipline que le noyau. Toute ambiguïté ou idée hors périmètre → note dans `cowork_workspace/requests/`, ne pas construire à la volée.
