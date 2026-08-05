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
$bd = Get-NetAdapter -Name "bdvpnservice_2" -ErrorAction SilentlyContinue
if (-not $bd) {
    Write-Output "  !! Interface bdvpnservice_2 ABSENTE — le VPN n'est pas connecte."
    Write-Output "  !! Le test ne prouverait rien. Connecte le VPN puis relance."
    exit 1
}
Write-Output "  interface : $($bd.Status) / $($bd.MediaConnectionState)"
$defaut = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
    Sort-Object RouteMetric | Select-Object -First 1
Write-Output "  route par defaut tenue par : $($defaut.InterfaceAlias) (metrique $($defaut.RouteMetric))"
if ($defaut.InterfaceAlias -notlike "*bdvpn*") {
    Write-Output "  !! Le VPN ne tient PAS la route par defaut — conditions du test non reunies."
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
