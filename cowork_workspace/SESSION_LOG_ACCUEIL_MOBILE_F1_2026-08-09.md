# SESSION LOG — Écran d'accueil mobile (F-1), 09/08/2026

## Périmètre

Brief : `cowork_workspace/BRIEF_ACCUEIL_MOBILE_F1.md`. Enrichir l'écran
d'accueil de la PWA mobile (orbe + liste compacte de 3-4 éléments + nav
basse à 4 entrées : Chat/Vision/Workspace/Réglages), sans nouveau backend
— réutilisation de `/workspace/summary` déjà exposé. Hors périmètre :
cadran générique de l'image de référence, appel téléphonique, rendu 3D/
GPU, nouvelle route API, modification du Workspace PC.

## Étape préalable

`/workspace/summary` expose déjà `reports`/`pending_requests` — rien à
construire côté serveur. Confirmé par `git diff` avant de committer :
zéro fichier `.py` modifié cette session.

## Ce qui a été construit

- `static/js/home.js` (nouveau) — classe `Home`, instanciée depuis
  `app.js` (même discipline que `ActivityConsole`/`DocumentsPanel`/...,
  pas un second `DOMContentLoaded` indépendant) : bascule accueil/chat,
  liste compacte (rapport + demande + raccourci vision), tiroirs Vision/
  Réglages.
- `static/index.html` — `#avatar-panel` devient un `<button>` (retour
  accueil), nouveau `#home-view`, `#chat-view` (wrapper), `#vision-drawer`,
  `#settings-drawer`, `#mobile-nav`.
- `static/css/style.css` — tokens ambre dupliqués (cohérence Workspace),
  styles accueil/nav/tiroirs.
- `static/sw.js` — `CACHE_NAME` v13→v15 (deux bumps, voir bug ci-dessous),
  `home.js` + `documents.js`/`finance.js` (oubli préexistant) ajoutés à
  `SHELL_FILES`.
- `ROADMAP.md` §5.80 — détail complet, dont les deux bugs réels trouvés
  en testant.

## 🔴 Bug réel #1 — clic transmis puis refermé aussitôt

"Réglages → État de sécurité" ouvrait puis refermait le popover dans le
même instant. Cause : `forwardClick()` synchrone déclenchait le clic
simulé PENDANT la remontée du clic d'origine — le gestionnaire "clic
extérieur" de `security.js` (sur `document`) voyait ensuite le clic
d'origine continuer sa remontée, cible hors badge/popover, et refermait
ce qui venait de s'ouvrir. Corrigé : `forwardClick()` diffère via
`setTimeout(fn, 0)`. Revérifié : popover reste ouvert.

## 🔴 Bug réel #2 — un Service Worker a mordu son propre auteur

Après avoir corrigé `home.js`, le retest échouait encore à l'identique.
`fetch(..., {cache:"no-store"})` renvoyait l'ANCIENNE version côté
navigateur, alors que `curl` direct contre le serveur renvoyait la
nouvelle. Cause : le Service Worker actif dans l'onglet de test servait
depuis un cache `lucas-shell-v14` peuplé AVANT le correctif (le bump v14
avait eu lieu avant cette édition de `home.js`, dans la même session) —
`sw.js` sert son cache en priorité, une option `no-store` côté page n'a
aucun effet sur ce qui se passe DANS le Service Worker. Corrigé par un
second bump (v14→v15). Leçon générale : re-bump à CHAQUE édition d'un
fichier de `SHELL_FILES`, même après un bump déjà fait plus tôt dans la
même session pour une autre raison.

## Vérifications réelles

- Aucun test Python nécessaire (zéro `.py` touché) ; suite complète
  revérifiée par prudence : 1594 passed, inchangé.
- Navigateur réel : séquence testée par clics réels + assertions sur
  l'état DOM (pas seulement visuel) — bascule accueil/chat, tiroir Vision
  (2 raccourcis), tiroir Réglages (5 renvois, dont sécurité après
  correctif). "Capture d'écran" vérifié bout en bout sur le VRAI serveur :
  message envoyé, avatar passé à "réfléchit" (pipeline vision réellement
  sollicité — réponse jamais affichée ici, elle aurait décrit l'écran réel
  de Cyril).
- Captures à l'appui, 412px (iframe) : accueil, chat actif, tiroir
  Réglages.
- Aucune régression : `git diff --stat` confirme zéro fichier Workspace/
  Sandbox touché ; PC Workspace et carte Sandbox rechargés et vérifiés à
  l'écran.

## État à la fin de la session

- Commit + push effectués (voir `git log`).
- `documents.js`/`finance.js` ajoutés à `SHELL_FILES` au passage (oubli
  préexistant, hors périmètre du brief mais trouvé en vérifiant cette
  liste avant d'y ajouter `home.js`).

## Pas encore fait

- Libellé "Réponses vocales" dans Réglages non synchronisé avec l'état
  réel (activé/désactivé) — cosmétique, le clic fonctionne correctement.
- Purge de l'historique navigateur pour le lien d'appairage — limite déjà
  connue (`app.js`, ROADMAP.md §5.33), sans rapport avec cette session.
