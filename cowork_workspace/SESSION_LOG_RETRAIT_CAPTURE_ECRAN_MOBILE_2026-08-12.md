# SESSION LOG — Retrait capture d'écran mobile + diagnostic déclenchement récurrent

**Date** : 12/08/2026
**Brief** : `cowork_workspace/BRIEF_RETRAIT_CAPTURE_ECRAN_MOBILE.md`
**Détail technique complet** : `ROADMAP.md` §5.92

## Contexte

Cyril signalait que la capture d'écran mobile (tiroir Vision, accueil mobile
F-1) se déclenchait de façon récurrente et gênante — "ça se déclenche tout
seul, en boucle". Le brief demandait explicitement de diagnostiquer la
cause AVANT tout retrait cosmétique, et de dire clairement si la cause
n'était pas dans le code de la capture elle-même.

## Ce qui a été trouvé — ce n'était pas le bouton mobile

Audit complet du chemin déclenché par le raccourci (`home.js::captureScreen()`
→ chat → `core/router.py`/`core/lucas_core.py` → `modules/vision_manager.py`) :
un seul clic envoie un seul message, aucune boucle, aucun minuteur, aucune
duplication d'écouteur.

La vraie cause : `lucas_daemon.py` capturait l'écran toutes les 30 secondes
et la webcam toutes les 5 minutes, en continu, 24/7, via une tâche planifiée
interne au daemon (`schedule.every(30).seconds.do(self.capture_screenshot)`,
`schedule.every(5).minutes.do(self.log_emotion)`) — présente depuis le tout
premier commit du dépôt, jamais journalisée dans `ROADMAP.md`. C'est la
fonctionnalité "Time Travel" du backlog `IDEAS.md` ("🎮 Modules fun & wow",
non priorisé), mais déjà codée et active dans le vrai daemon tournant en
tâche planifiée Windows persistante.

**Ce point a été signalé à Cyril avant toute action**, parce qu'il contredit
directement une décision déjà écrite dans `VISION_LONG_TERME.md` §4.2 :
la perception continue est explicitement "non activée [...] à n'activer que
par décision explicite, jamais par glissement progressif". Décision de
Cyril : désactiver les deux immédiatement.

## Correctifs appliqués

1. **`lucas_daemon.py`** — les deux tâches planifiées commentées dans
   `setup_schedule()`, méthodes `capture_screenshot`/`log_emotion`
   conservées (réactivation possible en une ligne, sur décision explicite
   future uniquement). Log de démarrage mis à jour.
2. **Daemon redémarré** (tâche planifiée `LucasDaemon`, Windows) pour que
   le correctif soit actif en mémoire, pas seulement dans le fichier source.
   Vérifié réellement : `data/screenshots/` n'a reçu aucun nouveau fichier
   pendant les 6 minutes suivant le redémarrage, contre un toutes les 30s
   avant correctif.
3. **`static/index.html`** — bouton "Capture d'écran" (`#vision-screen`)
   retiré du tiroir Vision. "Photo caméra" (`#vision-camera`) intact.
4. **`static/js/home.js`** — `captureScreen()`, `_appendVisionShortcut()`
   et le handler `#vision-screen` retirés ; nettoyage en cascade de
   `appendHomeAction()` et de deux champs (`textInput`/`inputForm`) devenus
   inutilisés.
5. **Pipeline serveur vérifié partagé avant tout retrait** (RT-2, jamais
   supposer) : `core/router.py::should_use_vision` et
   `core/lucas_core.py::_describe_screen` servent à toute question
   texte/vocale mentionnant l'écran, pas seulement à ce raccourci — rien
   retiré côté serveur.
6. **`static/sw.js`** — `CACHE_NAME` v20 → v21 (`index.html`/`home.js` sont
   dans `SHELL_FILES`).

## Trouvé en cours de route, non résolu — daemon dupliqué

En redémarrant le daemon, un second processus `lucas_daemon.py` apparaît
systématiquement à la même seconde, lancé via le Python **système**
plutôt que le `venv` de la tâche planifiée — reproduit 3 fois de suite, à
chaque redémarrage. Tuer ce second processus fait planter le premier, sans
trace d'exception dans le journal. Aucun `subprocess`/`multiprocessing`
trouvé dans `lucas_daemon.py` qui expliquerait un auto-relancement. Même
symptôme observé sur `LucasAPIServer` (uvicorn, deux instances en
parallèle) — probablement systémique, pas spécifique à ce fichier.
**Volontairement non résolu dans cette session** : hors périmètre du brief,
et déboguer à l'aveugle un service dont Cyril dépend au quotidien (pont
mobile) est plus risqué que de laisser les deux instances tourner sans
qu'elles ne capturent plus rien (le correctif du point 1 s'applique aux
deux, quel que soit l'interpréteur). À reprendre dans une session dédiée.

## Non vérifié, honnêtement

Le brief demandait un test réel sur mobile 412px, captures à l'appui.
L'extension Chrome (`claude-in-chrome`) n'était pas connectée dans cet
environnement pendant la session — impossible de charger la page et de
vérifier visuellement le tiroir Vision. Vérification faite autrement :
relecture directe du HTML/JS modifié, et recherche de toute référence
résiduelle à `captureScreen`, `vision-screen`, `appendHomeAction` (aucune
trouvée). Reste à confirmer par Cyril sur le vrai téléphone.
