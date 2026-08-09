# BRIEF DE SESSION — POSTE DE COMMANDEMENT IA (E-5)
**Pour : Claude Code | Rédigé par : Claude (Lead Architect) avec Cyril | Date : 09/08/2026**

---

## 1. Contexte

Cyril souhaite un espace dédié aux capacités de Luca's elle-même (par opposition aux données/résultats déjà affichés dans le Workspace). Il l'a nommé "Poste de Commandement IA" / "Bureau de l'IA".

**Cadrage important avant de commencer** : l'idée originale incluait "télécharger des compétences/connecteurs/plugins". Ce n'est PAS construit dans cette session — aucun mécanisme de chargement de plugin n'existe dans le projet actuellement. Construire une interface "télécharger" sans moteur réel derrière produirait une façade qui ne ferait rien. Cette session construit uniquement la V1 réaliste : un registre en lecture de ce qui existe déjà.

## 2. Objectif de la session

Une nouvelle icône dans le Workspace, menant à un module qui liste les capacités/modules actuellement actifs de Luca's, avec leur statut.

## 3. Étape préalable obligatoire

Explorer le code pour établir la liste réelle des modules actifs (pas une liste devinée) : `modules/`, `core/`, ce qui est réellement importé et fonctionnel. Distinguer ce qui est un vrai module opérationnel de ce qui est un fichier orphelin (voir l'audit de nettoyage du 09/08/2026 pour référence — ne pas lister ce qui a été identifié comme obsolète).

## 4. Périmètre

- Nouvelle icône/entrée dans le Workspace ("Poste de Commandement IA" ou "Bureau de l'IA" — Cyril tranchera le nom final s'il préfère autre chose).
- Module affichant, pour chaque capacité active identifiée à l'étape 3 : nom, brève description de ce qu'elle fait, statut (actif/inactif si détectable).
- Exemples de capacités à recenser (à confirmer par l'exploration, pas à supposer) : Finance CSV, OS Controller, Zone Sandbox, Détecteur d'économies, routeur hybride local/cloud, mémoire à 5 types, avatar.
- Lecture seule stricte — ce module n'installe, ne configure, ni ne modifie rien.
- Style Terminal Pro, cohérent avec le reste du Workspace (même palette ambre, même système modulaire déplaçable/redimensionnable si Cyril veut l'intégrer comme carte plutôt que comme page séparée — à clarifier en mode plan si ambigu).

## 5. Hors périmètre explicite de cette session

- ❌ Téléchargement, installation ou configuration de tout connecteur/skill/plugin — nécessite un mécanisme qui n'existe pas, session future dédiée une fois ce moteur construit.
- ❌ Modification des modules listés — affichage seul.
- ❌ Nouvelle capacité réelle pour Luca's — ce brief documente/expose l'existant, n'en ajoute pas.

## 6. Critères de validation

- Le nouveau point d'entrée est visible et accessible depuis le Workspace.
- La liste affichée correspond aux capacités réellement présentes et fonctionnelles dans le code (vérifié à l'étape 3, pas une liste statique écrite à la main sans vérification).
- Aucune action n'est possible depuis ce module au-delà de la consultation.
- Aucune régression sur le reste du Workspace.

Test réel avec captures à l'appui, PC et mobile. Commit, `ROADMAP.md` à jour, `SESSION_LOG.md` en fin de session.
