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

## Bloqué — même restriction que le 03-04/08/2026

Comme pour la création initiale de cette tâche, cet environnement n'a
pas les droits de modifier le Planificateur de tâches
(`schtasks /delete` a renvoyé "Accès refusé"). Rien n'a été cassé : la
tâche existante (`.vbs`) est intacte et vérifiée fonctionnelle
(`Dernier résultat: 0`) avant et après la tentative. Sa définition XML a
été sauvegardée avant toute tentative, dans le dossier scratchpad de
session (hors dépôt).

## Reste à faire par Cyril

Lancer lui-même, dans une invite (`cmd.exe` — syntaxe déjà testée avec
succès pour cette même tâche, voir §5.88) :

```
schtasks /delete /tn "LucasDaemon" /f
schtasks /create /tn "LucasDaemon" /tr "\"C:\OrionAI\venv\Scripts\pythonw.exe\" \"C:\OrionAI\lucas_daemon.py\"" /sc onlogon /rl limited /f
```

Puis vérifier :
- `schtasks /query /tn "LucasDaemon" /v /fo list` → `Dernier résultat: 0`
- Une nouvelle ligne dans `data/logs/daemon.log` après
  `schtasks /run /tn "LucasDaemon"`
- Aucune alerte Bitdefender (sans exception active)
- Idéalement un redémarrage réel du PC pour confirmer le déclencheur
  "à la connexion", pas seulement une relance à chaud

`start_daemon_hidden.vbs` n'a pas été supprimé — à retirer seulement une
fois la nouvelle méthode confirmée stable par Cyril.

## Point à trancher avec Cyril avant de continuer

Le même motif (`wscript.exe`+`.vbs`) équipe 4 autres services
(`LucasAPIServer`, veille modèles, Ollama, cowork requests). Cette
session ne touche qu'à `LucasDaemon`, conformément au brief — la
généralisation attend le retour de Cyril sur ce correctif, et une
vérification service par service (les autres n'ont pas forcément la
même propriété de chemins internes déjà absolus).

## Fichiers modifiés

- `ROADMAP.md` (§5.90)
- Aucun fichier de code modifié — la tâche planifiée elle-même n'a pas
  pu être touchée depuis cet environnement (accès refusé)
