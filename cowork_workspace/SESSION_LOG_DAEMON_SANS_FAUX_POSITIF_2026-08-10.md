# SESSION LOG — Daemon : mécanisme de démarrage sans faux positif antivirus

**Date** : 10/08/2026
**Brief** : `cowork_workspace/BRIEF_DAEMON_SANS_FAUX_POSITIF.md`
**Détail technique complet** : `ROADMAP.md` §5.90 (suite de §5.88)

## Contexte

La tâche planifiée `LucasDaemon` (`wscript.exe` → `.vbs` caché →
`pythonw.exe`) a été flaguée par Bitdefender ("ligne de commande
malveillante" / "application potentiellement malveillante"). Cyril a
retiré les deux exceptions ajoutées, par prudence — objectif de cette
session : un mécanisme qui ne ressemble pas à un motif de persistance
malveillante, sans dépendre d'une exception antivirus permanente.

## Ce qui a été trouvé

L'hypothèse posée par le brief lui-même ("le `.vbs` sert probablement à
masquer la fenêtre de console") **ne tenait pas** : le `.vbs` appelle
déjà `pythonw.exe`, qui n'ouvre aucune fenêtre par nature. La vraie
raison, documentée dans l'en-tête du `.vbs` et dans §5.88 : `schtasks
/create` n'a pas d'option pour fixer le répertoire de travail d'une
action, et la première version de la tâche passait le script en chemin
**relatif** — `pythonw.exe` ne le trouvait pas dans le répertoire de
travail par défaut du Planificateur.

En vérifiant `lucas_daemon.py` : le script n'a lui-même aucune
dépendance au répertoire de travail (chemins absolus partout,
`LUCAS_ROOT = Path("C:/OrionAI")` en tête de fichier). Donc pas besoin
de `cd /d` — il suffit de passer le **chemin absolu du script** en
argument à `pythonw.exe`. Ça élimine `cmd.exe` ET `wscript.exe`+`.vbs`
en une fois : un motif de tâche planifiée strictement plus simple que
ce qu'envisageait le brief, et plus simple encore que son plan de repli
("direct avec `cd /d`").

## Validé par Cyril en conditions réelles — 10/08/2026

Bloqué initialement par la même restriction que le 03-04/08/2026
(`schtasks /delete` → "Accès refusé" depuis cet environnement). Cyril a
lancé les deux commandes lui-même, puis **redémarré réellement le PC** :

- Nouvelle entrée dans `daemon.log` à 19:54:45, juste après le
  redémarrage — déclencheur "à la connexion" confirmé.
- **Aucune alerte Bitdefender**, testé sans exception active — objectif
  premier atteint.
- Tâches horaires observées ensuite (20:54:45, 21:54:46) — fonctionnement
  continu, pas juste un démarrage isolé.

Effet de bord noté en vérifiant : `Dernier résultat` affiche maintenant
`267009` (`SCHED_S_TASK_RUNNING`) au lieu de `0` en fonctionnement
normal — pas une erreur, juste un signal plus fidèle puisque
`pythonw.exe` est directement l'action de la tâche (avant, `wscript.exe`
rendait la main immédiatement après avoir détaché le vrai process).
Détail complet : `ROADMAP.md` §5.90.

`start_daemon_hidden.vbs` **supprimé** — méthode confirmée stable.

## 4 autres services — audités, aucun n'est le même cas

Cyril a demandé d'appliquer le même correctif partout sauf dépendance
réelle différente. Vérification faite en lisant chaque `.vbs` et le
script qu'il lance :

- **Ollama, veille modèles, cowork requests** (3 scripts PowerShell) —
  aucun chemin relatif, donc "pythonw.exe direct" ne s'applique même
  pas (pas de Python dans la chaîne). Le `.vbs` sert uniquement à
  masquer la fenêtre PowerShell ; l'équivalent natif
  (`-WindowStyle Hidden`) est documenté comme pouvant encore flasher
  brièvement selon la version — jamais vérifié sur cette machine.
- **LucasAPIServer** — `python.exe -m uvicorn ...` avec 3 dépendances
  réelles que le Daemon n'avait pas : résolution du module via
  `sys.path[0]` (= cwd), chemins relatifs pour cert/clé SSL, et
  redirection shell (`>>`) que `pythonw.exe` seul ne sait pas faire.

**Aucun correctif appliqué** à ces 4 services dans cette session — seul
le Daemon a été réellement flagué par Bitdefender à ce jour, pas
d'urgence à toucher des mécanismes qui fonctionnent pour un gain
préventif, avec un risque réel de casser un service utilisé au
quotidien (`LucasAPIServer` = pont mobile). Pistes concrètes par service
proposées dans `ROADMAP.md` §5.90, pour une session dédiée si Cyril la
valide.

## Fichiers modifiés

- `ROADMAP.md` (§5.90, mis à jour deux fois dans cette session)
- `start_daemon_hidden.vbs` — supprimé
- Aucun autre fichier de code touché
