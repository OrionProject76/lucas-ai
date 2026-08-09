# BRIEF DE SESSION — ZONE SANDBOX DU WORKSPACE (E-3)
**Pour : Claude Code | Rédigé par : Claude (Lead Architect) avec Cyril | Date : 09/08/2026**

---

## 1. Contexte

Le Workspace (E-1) est livré, stylé "Terminal pro" (ambre, glass léger, monospace), et modulaire (cartes déplaçables/redimensionnables). **Si le style Terminal Pro + la modularité (prompt précédent, cache-fix §5.74 inclus) n'ont pas encore été appliqués, faire cela d'abord — ce brief construit par-dessus, pas à la place.**

**Précision de périmètre importante** : Cyril a aussi demandé que le Workspace affiche "tous les modules au fil du temps" — ce point ne nécessite **aucun développement** dans cette session. La structure modulaire déjà en place absorbe naturellement chaque futur module (B-1, E-2, etc.) au moment de sa construction. Ne pas créer d'emplacements/cartes vides pour des modules qui n'existent pas encore.

## 2. Objectif de la session

Ajouter au Workspace une **zone sandbox** : un espace où Luca's peut écrire et exécuter du code (scripts, analyses, petits outils) en environnement isolé, visible et piloté par Cyril.

## 3. Étape préalable obligatoire

**Explorer avant de construire** : `CLAUDE.md` mentionne déjà "sandbox obligatoire pour toute exécution de code auto-généré" comme règle. Vérifier si un mécanisme d'exécution isolée existe déjà quelque part dans le projet (`modules/automation_manager.py` ou ailleurs) avant d'en construire un nouveau redondant. Documenter ce qui est trouvé (ou son absence) avant de proposer un plan.

## 4. Périmètre

- Nouvelle carte "Sandbox" dans le Workspace, cohérente avec les cartes existantes (même style, déplaçable/redimensionnable comme les autres).
- Affiche : le code proposé par Luca's (s'il y en a), son statut (en attente / exécuté / rejeté), le résultat de l'exécution (sortie standard, erreurs).
- Mécanisme d'exécution isolée, avec au minimum :
  - Pas d'accès réseau par défaut
  - Accès fichiers limité à un répertoire dédié (ex. `sandbox_workspace/`), jamais au code source de Luca's elle-même
  - Timeout d'exécution (éviter un script qui tourne indéfiniment)
  - Aucun droit d'écriture sur `core/`, `modules/`, `api/` ou tout autre dossier du code réel

## 5. Garde-fou non négociable (VISION_LONG_TERME §4, déjà acté — à respecter à la lettre)

Le code produit et exécuté ici reste **proposé**, jamais auto-déployé dans le code réel de Luca's. Toute intégration réelle d'un script utile passe par le circuit habituel : proposition → validation explicite de Cyril → intégration via une session Claude Code dédiée. La sandbox ne doit avoir **aucun mécanisme, même indirect, permettant d'écrire dans le code source de Luca's**.

## 6. Direction esthétique

Cohérente avec le reste du Workspace — Terminal pro (ambre `#f0a94e`, glass léger ~6-8px de flou, monospace, coins peu arrondis). Pas de nouvelle identité visuelle pour cette carte.

## 7. Exclusions explicites de cette session

- ❌ Emplacements/cartes spéculatifs pour des modules pas encore construits (voir §1)
- ❌ Accès de la sandbox à des données sensibles (finance, mémoire personnelle, fichiers hors `sandbox_workspace/`) — même règle RT-3 que partout ailleurs
- ❌ Tout mécanisme d'auto-modification du code de Luca's, même partiel ou différé

## 8. Critères de validation

- La carte Sandbox s'affiche, se déplace et se redimensionne comme les autres cartes du Workspace.
- Un script de test simple s'exécute dans l'environnement isolé et son résultat s'affiche correctement.
- Un script tentant d'accéder au réseau ou d'écrire hors de `sandbox_workspace/` échoue proprement (erreur visible, pas de crash silencieux).
- Aucune régression sur le reste du Workspace ou du chat.

Test réel avec captures à l'appui, sur mobile ET PC, comme les passes précédentes. Commit, `ROADMAP.md` à jour, `SESSION_LOG.md` en fin de session.
