# BRIEF DE SESSION — DÉTECTEUR D'ÉCONOMIES (B-2)
**Pour : Claude Code | Rédigé par : Claude (Lead Architect) avec Cyril | Date : 09/08/2026**

---

## 1. Contexte

Le module Finance CSV (import, catégorisation) est déjà fonctionnel. Ce brief l'étend avec une analyse qui repère les postes de dépense sur lesquels Cyril pourrait économiser — au service direct de l'objectif de capitalisation retraite (`SYNTHESE_IDEES_2026-08-08.md`, section B).

## 2. Objectif de la session

Analyser les imports CSV existants pour détecter : les charges récurrentes (abonnements), les doublons de charges, et les changements de montant sur une charge récurrente (hausse silencieuse de tarif).

## 3. Périmètre — ce qui est mécaniquement faisable depuis le CSV seul

1. **Détection de charges récurrentes** : même libellé/marchand + montant identique ou proche, à intervalle régulier (mensuel/annuel) sur plusieurs mois d'historique.
2. **Détection de doublons** : deux charges quasi identiques (même montant, même jour ou jours proches, libellé similaire) qui pourraient signaler un double prélèvement ou un abonnement oublié souscrit deux fois.
3. **Détection de hausse de tarif** : une charge récurrente déjà identifiée dont le montant augmente d'une occurrence à l'autre.
4. Restitution dans le Workspace : nouvelle carte "Détecteur d'économies", même style Terminal Pro que les 5 cartes existantes, même mécanisme modulaire (déplaçable/redimensionnable).

## 4. Hors périmètre explicite de cette session

- ❌ **Comparaison de fournisseurs** (énergie/télécom/assurance vs marché) — nécessiterait des données externes (recherche web, prix actuels) : session dédiée séparée si retenue, pas mécanique depuis le CSV seul.
- ❌ Toute connexion bancaire directe — reste exclu du projet (déjà acté).
- ❌ Modification du module Finance CSV existant au-delà de l'ajout de cette analyse — pas de refonte.
- ❌ E-2 (dataviz graphique) — cette session reste en liste/texte dans la carte Workspace, pas de graphique.

## 5. Contraintes à respecter

- **RT-3** : données financières strictement locales, jamais éligibles au cloud.
- **RT-2** : si la détection est incertaine (ex. deux charges qui se ressemblent mais pourraient être légitimes), le signaler comme "à vérifier", jamais affirmer une doublon/abonnement à tort. Pas de faux positif présenté avec assurance.
- Étape préalable : explorer le module Finance CSV existant (schéma des données, format des imports) avant d'écrire quoi que ce soit — même discipline que les briques précédentes.

## 6. Critères de validation

- Sur un jeu de données CSV réel (celui déjà importé par Cyril), le détecteur identifie au moins les charges récurrentes évidentes (abonnements connus).
- Un doublon simulé dans un jeu de test est détecté et signalé "à vérifier", pas affirmé comme certain.
- La carte Workspace affiche les résultats, cohérente visuellement avec les 5 cartes existantes.
- Aucune régression sur le Workspace ou les modules existants.

Test réel avec captures à l'appui, PC et mobile. Commit, `ROADMAP.md` à jour, `SESSION_LOG.md` en fin de session.
