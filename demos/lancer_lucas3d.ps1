# Lancement propre de Lucas3D - 07/08/2026
#
# /!\ CE FICHIER EST ENCODE EN UTF-8 AVEC BOM. Ne pas le reenregistrer
# sans. PowerShell 5.1 lit un .ps1 sans BOM en ANSI : les caracteres
# accentues et les tirets longs deviennent alors du charabia qui casse
# l'ANALYSE du script (rencontre en ecrivant ce fichier meme, le
# 07/08/2026 - " Jeton inattendu PID dans l'expression ").
#
# ⚠️ POURQUOI CE SCRIPT EXISTE
#
# Les lancements de la session Godot du 06-07/08 se faisaient par un
# `Start-Process` nu depuis le terminal de Claude Code. Un process enfant
# lance ainsi HERITE de la sortie standard de la console parente : la
# sortie de Godot se melangeait donc a celle du terminal de Cyril.
#
# Concretement, `websocket_client.gd` imprime " Connexion en cours... "
# puis " Reconnexion... " toutes les 3 secondes tant que la connexion
# echoue - et elle echoue toujours aujourd'hui (le client dit `ws://`
# alors que le serveur est en HTTPS, et n'envoie aucun jeton ; c'est
# l'etape 2). Mesure reelle : 773 lignes pendant l'etape 0, 518 pendant
# le test VRAM. Du bruit continu, dans le terminal de travail.
#
# Ce script coupe la source : stdout et stderr partent dans des fichiers,
# plus jamais dans la console.
#
# ⚠️ -RedirectStandardOutput et -RedirectStandardError ne peuvent PAS
# pointer le meme fichier (PowerShell 5.1 leve une erreur). D'ou deux
# fichiers distincts, et non un seul.
#
# A utiliser avec demos/arreter_lucas3d.bat (Bureau), qui est le filet de
# securite : il ne depend ni du rendu, ni du focus, ni de l'appli vivante.

param(
    [string]$Etiquette = "manuel",
    [string]$Binaire   = "C:\OrionAI\build\Lucas3D.exe"
)

$ErrorActionPreference = "Stop"
$dossier = "C:\OrionAI\data\logs"
if (-not (Test-Path $dossier)) { New-Item -ItemType Directory -Force $dossier | Out-Null }

$logGodot = Join-Path $dossier "godot_$Etiquette.log"      # --log-file (Godot)
$logOut   = Join-Path $dossier "godot_$Etiquette.out.txt"  # stdout capte
$logErr   = Join-Path $dossier "godot_$Etiquette.err.txt"  # stderr capte

if (-not (Test-Path $Binaire)) {
    Write-Output "  !! binaire introuvable : $Binaire"
    Write-Output "     (exporter d'abord : Godot.exe --headless --path Lucas3D --export-release ...)"
    exit 1
}

Start-Process -FilePath $Binaire `
    -ArgumentList '--verbose', '--log-file', $logGodot `
    -WorkingDirectory (Split-Path $Binaire) `
    -RedirectStandardOutput $logOut `
    -RedirectStandardError  $logErr

Start-Sleep -Seconds 6

$p = Get-Process -Name "Lucas3D" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($p) {
    Write-Output ("  Lucas3D lance - PID " + $p.Id + " | repond: " + $p.Responding)
    Write-Output ("  journal Godot : " + $logGodot)
    Write-Output ("  stdout capte  : " + $logOut)
    Write-Output "  (rien de tout cela ne s'affiche dans le terminal)"
} else {
    Write-Output "  !! Lucas3D n'a pas demarre - voir $logErr"
    exit 1
}
