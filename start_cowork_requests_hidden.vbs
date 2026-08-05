' start_cowork_requests_hidden.vbs
' Lance cowork_request_runner.ps1 sans fenetre visible.
'
' Cree le 05/08/2026 pour la tache planifiee "LucasCoworkRequests", qui
' remplace la tache Cowork de 22h — voir ROADMAP.md §5.51.
'
' Meme motif que start_server_hidden.vbs, et pour la meme raison : le
' Planificateur de taches n'a pas de reglage natif "fenetre cachee" pour
' une action arbitraire. WScript.Shell.Run(..., 0, False) lance la
' commande avec le style de fenetre 0 (cachee).
'
' Difference avec start_server_hidden.vbs : ici on ATTEND la fin (True au
' lieu de False). Le traitement est ponctuel, pas un service — et attendre
' permet au Planificateur de connaitre le vrai code de retour, donc de
' signaler un echec dans "Dernier resultat de la tache".
'
' -ExecutionPolicy Bypass : le script est local, ecrit dans le depot, et
' n'est pas signe. Bypass ne s'applique qu'a CET appel, jamais a la
' politique systeme.
Set objShell = CreateObject("WScript.Shell")
command = "powershell.exe -ExecutionPolicy Bypass -NoProfile -File " & _
    """C:\OrionAI\cowork_request_runner.ps1"""
objShell.Run command, 0, True
