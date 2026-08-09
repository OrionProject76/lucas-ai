# sandbox_workspace/

Répertoire dédié de la zone sandbox du Workspace (E-3,
`cowork_workspace/BRIEF_WORKSPACE_E3_SANDBOX.md`, `modules/sandbox_manager.py`).

Toute proposition de code exécutée depuis le Workspace tourne avec ce
dossier comme répertoire de travail — c'est la seule zone du disque à
laquelle un script sandboxé peut lire/écrire (voir les gardes dans
`modules/sandbox_runner.py`). Ce fichier `README.md` est le seul élément
suivi par Git : le reste (scripts proposés, fichiers produits par une
exécution) est généré et n'a rien à faire dans l'historique du projet.

Jamais le code source réel de Luca's (`core/`, `modules/`, `api/`, etc.) —
c'est précisément ce que ce dossier existe pour isoler.
