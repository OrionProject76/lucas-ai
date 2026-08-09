' start_daemon_hidden.vbs
' Lance le daemon de securite/rapports de Luca's (lucas_daemon.py) sans
' fenetre visible. Pas de redirection de sortie ici : lucas_daemon.py
' ecrit deja ses propres logs dans data\logs\daemon.log.
'
' Cree le 10/08/2026 pour la tache planifiee "LucasDaemon" (declencheur
' "a la connexion de l'utilisateur"). Voir ROADMAP.md pour le detail.
'
' Pourquoi un .vbs (meme raison que start_server_hidden.vbs) : schtasks
' /create n'a pas d'option native pour fixer le repertoire de travail
' d'une action -- sans le "cd /d" ci-dessous, pythonw.exe cherche
' lucas_daemon.py dans le repertoire de travail par defaut du
' Planificateur de taches (pas C:\OrionAI), et echoue immediatement
' (LastTaskResult=2, aucune ligne ecrite dans daemon.log -- confirme le
' 10/08/2026 avec la premiere version de la tache, creee sans ce fichier).
Set objShell = CreateObject("WScript.Shell")
command = "cmd.exe /c cd /d C:\OrionAI && venv\Scripts\pythonw.exe lucas_daemon.py"
objShell.Run command, 0, False
