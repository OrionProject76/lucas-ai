# cowork_workspace/requests/ — boîte à demandes

Dépose ici un fichier `.md` par demande (analyse, synthèse, comparatif, audit...).

## ⚙️ Traitement automatique (depuis le 05/08/2026)

Le protocole ci-dessous s'exécute **tout seul**, sans qu'il faille le
demander : tâche planifiée Windows **`LucasCoworkRequests`**, déclenchée à
l'ouverture de session **et** tous les jours à 22 h.

⚠️ **Remplace l'ancienne tâche Cowork de 22 h**, qui ne pouvait pas
fonctionner : les sessions Cowork tournent dans le cloud, sans accès au
pont bureau, donc sans accès à `C:\OrionAI`. Ce n'était pas une panne
réseau à dépanner mais une limite du produit — d'où le déplacement du
traitement vers Claude Code en local, là où les fichiers existent.
Détail complet : `ROADMAP.md` §5.51.

- Script : `cowork_request_runner.ps1` — journal dans
  `data/logs/cowork_requests.log`
- **Rien ne se lance s'il n'y a aucune demande en attente.** Sans fichier
  à traiter, la tâche lit un dossier et s'arrête.
- Le renommage en `_DONE` est fait par le script, jamais par le modèle.
- Une demande qui ne produit aucun rapport **reste en attente** plutôt
  que d'être marquée traitée — sinon elle disparaîtrait du radar sans
  rien avoir produit.

Pour désactiver : `Disable-ScheduledTask -TaskName "LucasCoworkRequests"`.

## Le protocole

Quand la tâche s'exécute — ou quand tu me demandes de "vérifier les
demandes" — je :
1. Lis chaque fichier `.md` qui ne porte pas encore le suffixe `_DONE`.
2. Exécute la tâche décrite (lecture seule sur `ROADMAP.md`, `CLAUDE.md`, `IDEAS.md`, `VISION_LONG_TERME.md` — jamais de modification de ces fichiers).
3. Dépose le résultat dans `cowork_workspace/reports/`.
4. Renomme la demande traitée en ajoutant `_DONE` à son nom.

Si une demande est ambiguë ou semble exiger de modifier un fichier protégé, je la laisse ici sans le suffixe `_DONE` et je dépose une note explicative dans `reports/` à la place.

*Ce fichier README peut être supprimé sans conséquence — il ne sert qu'à documenter le fonctionnement du dossier.*
