# BRIEF DE SESSION — MODE VOCAL CONTINU (MOBILE)
**Pour : Claude Code | Rédigé par : Claude (Lead Architect) avec Cyril | Date : 09/08/2026**

---

## 1. Contexte

L'accueil mobile (F-1) et le pont audio (`getUserMedia`) sont déjà fonctionnels. Aujourd'hui, parler à Luca's demande de cliquer le micro à chaque tour de parole. Objectif : une conversation mains libres, sans reclic à chaque phrase.

**Distinction importante à respecter à la lettre** : ce n'est PAS de la perception continue (refusée, conditionnée à Guardian/Privacy Shield — `VISION_LONG_TERME.md` §4.2). C'est un mode que Cyril active **explicitement**, pour la session en cours, jamais un service d'écoute permanent en arrière-plan.

## 2. Objectif de la session

Un mode "conversation" activable/désactivable sur mobile : une fois activé, Luca's écoute, détecte automatiquement quand Cyril parle (début/fin de phrase), transcrit, envoie, répond en voix, puis réécoute — sans clic entre chaque tour.

## 3. Étape préalable obligatoire

Explorer l'état réel du pipeline STT actuel (comment le bouton micro existant capture/transcrit aujourd'hui) avant de construire par-dessus. Vérifier si un mécanisme de détection d'activité vocale (VAD) existe déjà quelque part dans le projet (PC ou mobile) — ne pas en réécrire un si un existe.

## 4. Périmètre

- Un bouton/toggle clair "Mode conversation" — activation et désactivation explicites, jamais un état par défaut.
- Détection d'activité vocale pour segmenter automatiquement la parole (démarrer/arrêter l'enregistrement d'un tour sans clic).
- Cycle automatique : écoute → transcription → envoi → réponse vocale → retour à l'écoute.
- **Arrêt automatique après une période d'inactivité raisonnable** (pas d'écoute qui continue indéfiniment si Cyril ne parle plus) — durée à proposer en mode plan, pas à deviner arbitrairement.
- Indicateur visuel clair de l'état (écoute / traite / répond) — réutiliser les états de l'orbe déjà existants plutôt qu'en inventer de nouveaux.
- Bouton d'arrêt immédiat toujours visible et accessible pendant que le mode est actif.

## 5. Hors périmètre explicite de cette session

- ❌ Mot d'éveil ("Hey Luca's") pour activer le mode sans toucher l'écran — v1 reste à activation manuelle par toggle, évolution possible plus tard.
- ❌ Activation automatique du mode au démarrage de l'app ou dans un contexte donné — toujours un geste explicite de Cyril.
- ❌ Toute forme de perception/écoute qui persisterait après fermeture de l'app ou mise en arrière-plan prolongée.
- ❌ Modification du Workspace PC ou de l'écran d'accueil mobile existant au-delà de l'ajout du toggle.

## 6. Contraintes

- Consommation batterie : l'écoute continue sollicite micro/CPU en permanence pendant le mode actif — documenter honnêtement l'impact réel mesuré, ne pas le minimiser.
- Bump `CACHE_NAME` si un fichier `SHELL_FILES` est modifié.
- RT-3 : le flux audio/transcrit suit les mêmes règles de sensibilité que le reste (si une donnée sensible apparaît dans une transcription, mêmes garde-fous que le chat texte).

## 7. Critères de validation

- Le mode s'active/se désactive clairement, jamais par défaut.
- Une conversation de plusieurs tours fonctionne sans clic entre les tours.
- L'arrêt automatique après inactivité fonctionne réellement (testé, pas supposé).
- Le bouton d'arrêt immédiat fonctionne à tout moment pendant le mode actif.
- Aucune régression sur le chat texte, la caméra, ou le reste de l'accueil mobile.

Test réel avec captures/enregistrement à l'appui, sur mobile. Commit, `ROADMAP.md` à jour, `SESSION_LOG.md` en fin de session.
