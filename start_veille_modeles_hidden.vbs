' start_veille_modeles_hidden.vbs
' Lance veille_modeles_runner.ps1 sans fenetre visible.
'
' Cree le 05/08/2026 pour la tache planifiee "LucasVeilleModeles".
' Meme motif que start_server_hidden.vbs, start_cowork_requests_hidden.vbs
' et start_ollama_hidden.vbs : le Planificateur n'a pas de reglage natif
' "fenetre cachee" pour une action arbitraire.
'
' Attend la fin (True) : la passe est ponctuelle et le Planificateur doit
' connaitre son vrai code de retour. Une veille dure plusieurs minutes —
' c'est normal, elle telecharge et mesure des modeles.
Set objShell = CreateObject("WScript.Shell")
command = "powershell.exe -ExecutionPolicy Bypass -NoProfile -File " & _
    """C:\OrionAI\veille_modeles_runner.ps1"""
objShell.Run command, 0, True
