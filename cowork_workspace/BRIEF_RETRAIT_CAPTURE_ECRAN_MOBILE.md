# BRIEF DE SESSION — RETRAIT CAPTURE D'ÉCRAN MOBILE + DIAGNOSTIC DÉCLENCHEMENT RÉCURRENT
**Pour : Claude Code | Rédigé par : Claude (Lead Architect) avec Cyril | Date : 12/08/2026**

---

## 1. Contexte

Cyril signale que la capture d'écran mobile (tiroir Vision, accueil mobile F-1) se déclenche de façon **récurrente et gênante**, sans qu'il l'ait demandée à chaque fois — pas juste "je n'en veux plus", mais "ça se déclenche tout seul, en boucle". Ça contredit directement la règle posée dès le départ pour la vision mobile : capture à la demande explicite uniquement, jamais en continu (`VISION_LONG_TERME.md` §4.2). Objectif double : retirer la fonction ET comprendre pourquoi elle se comportait mal, pas juste masquer le symptôme.

Décision actée par ailleurs (contexte, pas à reconstruire ici) : la lecture d'écran mobile réelle reste hors de portée d'une PWA — ce n'est faisable que via une vraie app Android native (D-7, déjà catalogué, reporté à plus tard dans les priorités de Cyril).

## 2. Objectif de la session

1. **Diagnostiquer la cause du déclenchement récurrent** — priorité absolue, avant tout retrait cosmétique.
2. **Retirer le raccourci "Capture d'écran"** du tiroir Vision de l'accueil mobile.
3. **Garder intact le raccourci Caméra** (capture photo via l'appareil photo) — ne pas y toucher.

## 3. Étape préalable obligatoire — diagnostic avant correctif

Avant de retirer quoi que ce soit, comprends pourquoi ça se déclenchait en boucle. Pistes à vérifier, sans se limiter à celles-ci :
- Un minuteur/intervalle JS qui redéclenche la capture périodiquement (bug de boucle, pas un vrai minuteur voulu).
- Un message serveur (WebSocket) renvoyé plusieurs fois pour une seule vraie demande, réinterprété comme plusieurs demandes côté client.
- Un lien avec le délai avant capture ajouté récemment (§5.85 ou proche) — vérifier s'il déclenche plusieurs fois au lieu d'une.
- Toute trace de capture d'écran demandée par le serveur sans action explicite de Cyril (ce qui serait un vrai problème de confidentialité, à traiter avec la plus grande sérieux si trouvé).

Documente la cause réelle trouvée avant de passer au retrait — si la cause n'est pas dans le code de la capture elle-même mais ailleurs (ex. une tâche cron, un test resté actif), dis-le clairement plutôt que de supposer que le retrait du bouton suffit à tout régler.

## 4. Périmètre du retrait

- Retire le raccourci "Capture d'écran" du tiroir Vision (`static/js/home.js` ou équivalent selon ce que le diagnostic révèle).
- Vérifie qu'aucun mécanisme ne continue à tourner en arrière-plan après le retrait (le vrai risque : enlever le bouton sans couper la cause réelle, qui continuerait à se déclencher invisiblement).
- Le raccourci Caméra doit rester identique, aucune régression sur son fonctionnement.
- Nettoie le pipeline serveur de capture d'écran mobile s'il devient inutilisé par le retrait (mais vérifie d'abord qu'il n'est pas partagé avec autre chose avant de le retirer — RT-2, jamais supposer).

## 5. Hors périmètre explicite

- ❌ Le pont micro/caméra téléphone → Luca's PC (nouvelle idée de Cyril) — brief séparé, pas cette session.
- ❌ D-7 (app Android native, lecture d'écran réelle) — reste reporté.
- ❌ Toute modification de la caméra/photo mobile au-delà de vérifier qu'elle continue de fonctionner.

## 6. Critères de validation

- Cause du déclenchement récurrent identifiée et documentée, pas seulement supposée.
- Raccourci "Capture d'écran" absent du tiroir Vision après le changement.
- Aucun déclenchement de capture d'écran résiduel après le retrait (testé en conditions réelles, pas juste en lisant le code).
- Caméra toujours fonctionnelle, testée en conditions réelles.
- Bump `CACHE_NAME` si un fichier `SHELL_FILES` est modifié.

Test réel sur mobile 412px, captures à l'appui. Commit, `ROADMAP.md` à jour, `SESSION_LOG.md` en fin de session.
