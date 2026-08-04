' start_server_hidden.vbs
' Lance le serveur FastAPI/uvicorn de Luca's sans fenetre visible, avec les
' sorties standard/erreur redirigees vers data\logs\server_startup.log.
'
' Cree le 05/08/2026 pour la tache planifiee "LucasAPIServer" (declencheur
' "a la connexion de l'utilisateur"). Voir ROADMAP.md pour le detail complet
' et la procedure de desactivation/suppression.
'
' Pourquoi un .vbs : le Planificateur de taches n'a pas de reglage natif
' "fenetre cachee" pour une action arbitraire, et redirection (>>) exige un
' interpreteur shell (cmd.exe). WScript.Shell.Run(..., 0, False) lance la
' commande cmd.exe demandee avec le style de fenetre 0 (cachee) et sans
' attendre sa fin (False) : ni le cmd.exe ni le python.exe enfant n'affichent
' de fenetre, contrairement a "start /min" qui reste visible dans la barre
' des taches.
Set objShell = CreateObject("WScript.Shell")
command = "cmd.exe /c cd /d C:\OrionAI && " & _
    "venv\Scripts\python.exe -m uvicorn api.server:app --host 0.0.0.0 --port 8000 " & _
    "--ssl-certfile data/cert.pem --ssl-keyfile data/key.pem " & _
    ">> data\logs\server_startup.log 2>&1"
objShell.Run command, 0, False
