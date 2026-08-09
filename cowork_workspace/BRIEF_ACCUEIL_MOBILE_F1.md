# BRIEF DE SESSION — ÉCRAN D'ACCUEIL MOBILE (F-1)
**Pour : Claude Code | Rédigé par : Claude (Lead Architect) avec Cyril | Date : 09/08/2026**

---

## 1. Contexte

Le Workspace PC (5 cartes, style Terminal Pro) est livré. Cyril a fourni une image de référence (app mobile sombre, accent doré, liste d'éléments cliquables, barre de navigation basse) et souhaite que l'écran d'accueil mobile de Luca's atteigne le même niveau de richesse fonctionnelle que le Workspace, adapté au format téléphone.

## 2. Objectif de la session

Enrichir l'écran d'accueil de la PWA mobile (actuellement : orbe d'état + ligne de saisie seuls) avec une liste d'éléments récents et une navigation basse, sans dupliquer un nouveau backend — réutilisation de ce que `workspace_manager` expose déjà.

## 3. Périmètre

1. **Conserver l'orbe d'état de l'avatar** en haut de l'écran, tel qu'il existe (Écoute/Parle/Réfléchit/etc.) — ne pas le remplacer par un cadran décoratif.
2. **Liste compacte sous l'orbe** : 3-4 éléments récents maximum, format icône + titre + méta (même schéma visuel que les cartes du Workspace) —
   - Dernier rapport (`workspace_manager` → `reports`)
   - Demande en attente la plus récente (`requests` non `_DONE`)
   - Raccourci direct vers un mode vision (ex. "Capture d'écran")
   Données réelles via l'API déjà existante (`/workspace/summary` ou équivalent) — pas de nouvelle logique métier, uniquement une vue mobile de ce qui existe.
3. **Barre de navigation basse**, 4 entrées : Chat (écran actuel), Vision (accès direct aux modes de capture), Workspace (lien vers `workspace.html`, déjà responsive — vérifié fonctionnel à 412px lors des sessions précédentes), Réglages.
4. **Style** : palette ambre "Terminal pro" déjà en place sur le Workspace, cohérence totale — pas de nouvelle identité visuelle. Glow statique, pas de clignotement (règle déjà posée).

## 4. Hors périmètre explicite

- ❌ Reproduire le cadran circulaire générique de l'image de référence — l'orbe d'état existant le remplace, il a un sens fonctionnel que l'image de référence n'a pas.
- ❌ Fonction d'appel téléphonique (reste annulée, A-3).
- ❌ Graphe 3D ou tout rendu nécessitant du GPU.
- ❌ Nouvelle route API si `workspace_manager` expose déjà les données nécessaires — vérifier avant de coder (étape d'exploration obligatoire).
- ❌ Modifier le Workspace PC lui-même dans cette session.

## 5. Contraintes techniques

- Bump `CACHE_NAME` dans `static/sw.js` si `index.html`/`style.css`/tout `.js` de l'app shell mobile est modifié — leçon déjà documentée (§5.74), ne pas oublier.
- Zéro VRAM, zéro rendu 3D.
- `createElement`/`textContent`, jamais `innerHTML` sur contenu dynamique — même discipline que le reste du projet.

## 6. Critères de validation

- Écran d'accueil mobile affiche l'orbe + la liste de 3-4 éléments réels (pas simulés) + la barre de navigation.
- Navigation basse fonctionnelle : chaque bouton mène au bon écran.
- Testé réellement à largeur mobile (412px), captures à l'appui.
- Aucune régression sur le chat existant, le Workspace PC, ou la carte Sandbox.

Commit, `ROADMAP.md` à jour, `SESSION_LOG.md` en fin de session.
