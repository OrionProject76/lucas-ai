# verif_coexistence_vpn.ps1 — Tailscale et le VPN Bitdefender ensemble
#
# À lancer AVEC LE VPN BITDEFENDER CONNECTÉ, après avoir exclu
# tailscaled.exe du tunnel (split tunneling). Voir ROADMAP.md §5.54.
#
# ⚠️ Le point 1 conditionne tous les autres : sans lui, un test
# « réussi » pourrait simplement refléter un VPN déconnecté — donc ne
# rien prouver du tout sur la coexistence.

$ErrorActionPreference = "Continue"
$ts = "C:\Program Files\Tailscale\tailscale.exe"
$IP_TAILSCALE_PC = "100.88.249.117"
$IP_TAILSCALE_TEL = "100.91.76.4"

function Titre($t) { Write-Output ""; Write-Output "=== $t ===" }

# ── 1. Le VPN est-il RÉELLEMENT actif ? ───────────────────────────────
Titre "1. Le VPN Bitdefender capture-t-il bien la route par defaut ?"
# ⚠️ Filtre sur le MOTIF, jamais sur un nom exact. Premiere version codait
# "bdvpnservice_2" en dur : au premier test reel, l'interface s'appelait
# "bdvpnservice_1" et le script a conclu "VPN deconnecte" alors qu'il
# tournait. Le suffixe change a chaque reconnexion, l'adresse aussi
# (100.112.1.249 -> 100.112.10.167). Un identifiant volatil code en dur,
# exactement le motif traque toute la journee.
$bd = Get-NetAdapter | Where-Object {
    $_.Name -like "bdvpnservice*" -and $_.Status -eq "Up"
} | Select-Object -First 1

if (-not $bd) {
    Write-Output "  !! Aucune interface bdvpnservice* active — le VPN n'est pas connecte."
    Write-Output "  !! Le test ne prouverait rien. Connecte le VPN puis relance."
    exit 1
}
Write-Output "  interface : $($bd.Name) — $($bd.Status) / $($bd.MediaConnectionState)"
$ipVpn = (Get-NetIPAddress -InterfaceAlias $bd.Name -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress
Write-Output "  adresse   : $ipVpn"
Write-Output "  --- toutes les routes par defaut, par metrique ---"
Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
    Sort-Object RouteMetric |
    ForEach-Object { Write-Output "    $($_.InterfaceAlias.PadRight(16)) metrique $($_.RouteMetric)" }

$defaut = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
    Sort-Object RouteMetric | Select-Object -First 1

# ⚠️ Ce releve TRANCHE une question restee ouverte (ROADMAP.md §5.54) :
# le mecanisme du conflit a ete DECRIT comme une capture de la route par
# defaut, mais jamais MESURE — la table n'avait pas ete relevee pendant
# que le VPN etait connecte. Deux issues, deux mecanismes differents :
#
#   - le VPN tient 0.0.0.0/0  -> capture de route confirmee
#   - il ne la tient pas       -> c'est un FILTRAGE APPLICATIF
#     (bdntwrk ou le kill-switch), et l'explication d'origine etait
#     fausse meme si le correctif reste le bon
#
# Le profil observe (UDP mort, TCP vers les memes destinations vivant)
# penche deja vers le filtrage : une capture de route enverrait l'UDP
# DANS le tunnel, ou il fonctionnerait generalement.
if ($defaut.InterfaceAlias -like "*bdvpn*") {
    Write-Output "  => MECANISME : capture de la route par defaut CONFIRMEE"
} else {
    Write-Output "  => MECANISME : le VPN ne tient PAS 0.0.0.0/0."
    Write-Output "     L'explication par capture de route est donc FAUSSE :"
    Write-Output "     il s'agit d'un filtrage applicatif (bdntwrk / kill-switch)."
}

# ── 2. Tailscale se voit-il en ligne ? ────────────────────────────────
Titre "2. tailscale status"
$statut = & $ts status 2>&1
$statut | ForEach-Object { Write-Output "  $_" }
$horsLigne = $statut -match "lucas-project.*offline"
$sante = $statut -match "Health check"
Write-Output ""
Write-Output "  PC hors ligne        : $([bool]$horsLigne)   (attendu False)"
Write-Output "  avertissement sante  : $([bool]$sante)   (attendu False)"

# ── 3. UDP et decouverte d'adresse ────────────────────────────────────
Titre "3. tailscale netcheck"
$net = & $ts netcheck 2>&1 | Select-String -Pattern "UDP:|IPv4:|Nearest DERP"
$net | ForEach-Object { Write-Output "  $($_.Line.Trim())" }

# ── 4. Joignabilite du pair ───────────────────────────────────────────
Titre "4. tailscale ping vers le telephone"
& $ts ping --timeout=8s --c=3 $IP_TAILSCALE_TEL 2>&1 | ForEach-Object { Write-Output "  $_" }

# ── 5. Luca's est-elle joignable via Tailscale ? ──────────────────────
Titre "5. Acces reel a Luca via l'adresse Tailscale"
$code = & curl.exe -k -s -o NUL -m 15 -w "%{http_code}" "https://${IP_TAILSCALE_PC}:8000/status"
Write-Output "  GET /status -> HTTP $code"
$code2 = & curl.exe -k -s -o NUL -m 15 -w "%{http_code}" "https://${IP_TAILSCALE_PC}:8000/app/"
Write-Output "  GET /app/   -> HTTP $code2"

Write-Output ""
Write-Output "=== Verdict ==="
if (-not $horsLigne -and -not $sante -and $code -eq "200") {
    Write-Output "  COEXISTENCE FONCTIONNELLE : VPN actif, Tailscale en ligne, Luca joignable."
} else {
    Write-Output "  Coexistence NON confirmee — voir les points ci-dessus."
}
