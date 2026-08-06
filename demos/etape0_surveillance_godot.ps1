# Etape 0 de la session Godot supervisee (06/08/2026) — CAPTURER UNE TRACE.
#
# Objectif : NE PAS corriger. Obtenir une trace d'une fermeture ou d'un gel
# spontane de Godot, ce que les 4 occurrences du 02/08/2026 n'ont jamais
# laisse (rien dans le journal d'evenements Windows, ni « Application
# Error » ni « Application Hang »).
#
# Ce que ce script echantillonne toutes les 5 s, et POURQUOI :
#   - Responding : c'est LUI qui distingue « disparu » de « GELE ». Les
#     deux cas se sont produits le 02/08 et ne se diagnostiquent pas
#     pareil. Un process vivant mais Responding=False est un gel.
#   - VRAM + modele Ollama charge : la piste n^o 2 de la checklist du
#     05/08 est un pic VRAM pendant un chargement de modele. Sans releve
#     horodate en parallele, la correlation est inverifiable apres coup.
#   - handles / threads : une fuite lente se verrait ici avant le crash.
#
# Le binaire est lance separement avec --verbose --log-file : un binaire
# release Windows n'a pas de console attachee, sa sortie standard est
# perdue. --log-file est le seul moyen de la garder.

param(
    [int]$DureeMinutes = 30,
    [string]$Csv = "C:\OrionAI\data\logs\etape0_godot_surveillance.csv"
)

$ErrorActionPreference = "Continue"
$fin = (Get-Date).AddMinutes($DureeMinutes)

"horodatage;secondes;vivant;repond;vram_mo;modele_ollama;handles;threads" |
    Out-File -FilePath $Csv -Encoding utf8

$debut = Get-Date
$dejaMort = $false

while ((Get-Date) -lt $fin) {
    $p = Get-Process -Name "Lucas3D" -ErrorAction SilentlyContinue | Select-Object -First 1
    $vivant = $null -ne $p
    $repond = if ($vivant) { $p.Responding } else { "-" }
    $handles = if ($vivant) { $p.HandleCount } else { "-" }
    $threads = if ($vivant) { $p.Threads.Count } else { "-" }

    $vram = (& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) -join ""
    $modele = (& ollama ps | Select-Object -Skip 1 | ForEach-Object { ($_ -split "\s+")[0] }) -join ","
    if (-not $modele) { $modele = "aucun" }

    $s = [math]::Round(((Get-Date) - $debut).TotalSeconds)
    "$(Get-Date -Format 'HH:mm:ss');$s;$vivant;$repond;$vram;$modele;$handles;$threads" |
        Out-File -FilePath $Csv -Append -Encoding utf8

    # Un gel se signale immediatement : il n'y a pas de raison d'attendre
    # la fin de la fenetre de surveillance pour le savoir.
    if ($vivant -and -not $p.Responding) {
        "!! GEL DETECTE a t+$s s (process vivant, ne repond plus)" |
            Out-File -FilePath $Csv -Append -Encoding utf8
    }
    if (-not $vivant -and -not $dejaMort) {
        "!! PROCESS DISPARU a t+$s s" | Out-File -FilePath $Csv -Append -Encoding utf8
        $dejaMort = $true
    }

    Start-Sleep -Seconds 5
}
