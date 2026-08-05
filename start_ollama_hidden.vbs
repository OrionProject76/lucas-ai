' start_ollama_hidden.vbs
' Lance ollama_server_runner.ps1 sans fenetre visible.
'
' Cree le 05/08/2026 pour la tache planifiee "LucasOllamaServer".
' Meme motif que start_server_hidden.vbs et
' start_cowork_requests_hidden.vbs : le Planificateur n'a pas de reglage
' natif "fenetre cachee" pour une action arbitraire.
'
' Attend la fin (True) comme le lanceur des demandes Cowork, et
' contrairement a celui du serveur API : le script est ponctuel — il
' verifie, demarre si besoin, et rend la main. Attendre permet au
' Planificateur de connaitre le vrai code de retour.
'
' ⚠️ Le serveur Ollama lui-meme, lui, est lance en Start-Process detache
' DANS le script : il doit survivre a la fin de cette tache.
Set objShell = CreateObject("WScript.Shell")
command = "powershell.exe -ExecutionPolicy Bypass -NoProfile -File " & _
    """C:\OrionAI\ollama_server_runner.ps1"""
objShell.Run command, 0, True
