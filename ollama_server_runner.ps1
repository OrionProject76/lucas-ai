# ollama_server_runner.ps1 — garantit qu'un serveur Ollama tourne
#
# ── Pourquoi ce script existe (05/08/2026) ────────────────────────────
#
# Luca s'est retrouvee cassee en pleine utilisation : « Modele
# gpt-oss:20b introuvable ». Cause — l'application tray d'Ollama avait
# repris la main et servait un magasin de modeles imbriqué ne contenant
# que 2 modeles sur 13 (ROADMAP.md §5.36).
#
# ⚠️ Le demarrage automatique n'etait PAS en cause. Verifie : Ollama.lnk
# est dans Startup-Disabled depuis le 02/08, aucune cle Run, aucune tache
# planifiee, rien dans server.json.
#
# Le vrai mecanisme, etabli par test : **la CLI Ollama lance
# l'application tray quand aucun serveur ne repond**. Verifie dans les
# deux sens — avec un serveur deja en ecoute, `ollama list` ne lance
# rien ; sans serveur, l'appli tray reapparait.
#
# Le correctif ne consiste donc pas a desactiver quelque chose, mais a
# garantir qu'un serveur repond TOUJOURS. La CLI n'a alors plus jamais de
# raison de reveiller l'appli tray, et le magasin servi reste le bon.
#
# ── Garde ─────────────────────────────────────────────────────────────
#
# Ne demarre rien si un serveur ecoute deja. Lancer un second `ollama
# serve` echouerait a prendre le port et sortirait en erreur — bruit
# inutile dans le journal, et surtout un « echec » trompeur alors que
# tout va bien.

$ErrorActionPreference = "Stop"

$Log = "C:\OrionAI\data\logs\ollama_server.log"
New-Item -ItemType Directory -Force -Path (Split-Path $Log) | Out-Null

function Ecrire($message) {
    Add-Content -Path $Log -Encoding utf8 -Value (
        "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $message
    )
}

$enEcoute = Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue
if ($enEcoute) {
    Ecrire "un serveur ecoute deja sur 11434 (PID $($enEcoute[0].OwningProcess)) — rien a faire"
    exit 0
}

Ecrire "aucun serveur sur 11434 — demarrage de 'ollama serve'"

Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden `
    -RedirectStandardOutput "C:\OrionAI\data\logs\ollama_serve.log" `
    -RedirectStandardError  "C:\OrionAI\data\logs\ollama_serve.err.log"

# Laisser le temps au serveur d'ouvrir son port avant de conclure.
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 1
    $ok = Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue
    if ($ok) {
        Ecrire "serveur demarre (PID $($ok[0].OwningProcess))"
        # Controle utile : un magasin ampute est le symptome d'origine.
        # Le compter ici donne un signal exploitable dans le journal.
        try {
            $modeles = (& ollama list 2>$null | Select-Object -Skip 1 | Where-Object { $_.Trim() }).Count
            Ecrire "modeles visibles : $modeles"
            if ($modeles -lt 5) {
                Ecrire "!! ALERTE : seulement $modeles modele(s) — magasin probablement ampute (ROADMAP.md 5.36)"
            }
        } catch {
            Ecrire "modeles visibles : indeterminé"
        }
        exit 0
    }
}

Ecrire "!! le serveur n'ecoute toujours pas apres 15 s"
exit 1
