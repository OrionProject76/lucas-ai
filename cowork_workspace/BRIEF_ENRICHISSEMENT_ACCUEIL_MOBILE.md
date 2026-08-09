# BRIEF DE SESSION — ENRICHISSEMENT ACCUEIL MOBILE
**Pour : Claude Code | Rédigé par : Claude (Lead Architect) avec Cyril | Date : 10/08/2026**

---

## 1. Contexte

L'accueil mobile (F-1) affiche aujourd'hui : orbe d'état + liste compacte de 3 éléments fixes (dernier rapport, demande en attente la plus récente, raccourci vision) + nav basse. Depuis sa construction, le Workspace PC s'est enrichi (6 cartes : Rapports, Demandes, Actions, Objectifs, Sandbox, Détecteur d'économies) et le Bureau de l'IA (E-5) est apparu. L'accueil mobile n'a pas suivi cette croissance — il reste figé sur son contenu d'origine.

## 2. Objectif de la session

Enrichir la liste compacte de l'accueil mobile pour refléter la richesse réelle du Workspace, sans la transformer en second Workspace complet (ce rôle reste à la page Workspace elle-même, déjà accessible via la nav).

## 3. Étape préalable obligatoire

Explorer ce que `/workspace/summary` expose déjà côté serveur (reports, requests, recent_actions, objectives, sandbox_runs, savings) avant de proposer quoi ajouter — ne pas deviner les champs disponibles.

## 4. Périmètre

- Étendre la liste de l'accueil mobile au-delà des 3 éléments fixes actuels, en piochant dans les données déjà exposées par `/workspace/summary` (même source que le Workspace PC, pas de nouvelle route).
- Candidats à intégrer, à confirmer en mode plan selon ce que l'exploration révèle comme pertinent et compact à afficher sur petit écran : compteur de demandes en attente, alertes du détecteur d'économies, propositions sandbox en attente de décision.
- Garder le format compact — badges/compteurs plutôt que le détail complet de chaque élément (le détail reste dans le Workspace complet, un clic plus loin).
- Même style Terminal Pro déjà en place sur l'accueil mobile.

## 5. Hors périmètre explicite de cette session

- ❌ D-7 (lecture d'écran smartphone) — session dédiée séparée, domaine technique différent (app Android native), pas mélangé à ce chantier web.
- ❌ Modification du Workspace PC lui-même.
- ❌ Nouvelle route API si `/workspace/summary` suffit déjà — vérifier avant d'en ajouter une.
- ❌ Toucher au mode conversation ou aux tiroirs Vision/Réglages déjà en place.

## 6. Contraintes

- Bump `CACHE_NAME` si un fichier `SHELL_FILES` est modifié (leçon §5.74/§5.85).
- RT-2 : si une donnée est absente/vide, l'afficher comme telle plutôt que de simuler un contenu.
- Zéro VRAM, zéro rendu 3D.

## 7. Critères de validation

- L'accueil mobile affiche plus que les 3 éléments d'origine, avec des données réelles (pas simulées).
- Reste lisible et compact à 412px, sans surcharger l'écran.
- Aucune régression sur le mode conversation, la nav, le Workspace PC.

Test réel avec captures à l'appui, mobile 412px. Commit, `ROADMAP.md` à jour, `SESSION_LOG.md` en fin de session.
