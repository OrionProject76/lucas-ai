# veille_modeles_runner.ps1 — veille hebdomadaire LLM + VLM
#
# ── Pourquoi ce script existe (05/08/2026) ────────────────────────────
#
# Regle 12 de CLAUDE.md : la recherche du meilleur compromis
# performance/qualite est continue, et traite LLM et VLM ENSEMBLE dans
# la meme passe. Cyril a demande une cadence hebdomadaire, jusqu'a ce
# qu'il indique explicitement que le choix final est fait.
#
# Pas via Cowork, pour la raison deja documentee
# (workflow_requests_reports.md) : les taches planifiees cloud n'ont
# structurellement aucun acces au pont bureau, donc aucun acces a
# C:\OrionAI. Meme schema que LucasAPIServer : une tache planifiee
# Windows LOCALE qui appelle Claude Code en non-interactif.
#
# ── ⚠️ CETTE TACHE EST PLUS PRIVILEGIEE QUE cowork_request_runner.ps1 ──
#
# Le traitement des demandes Cowork tourne avec Read/Glob/Grep/Write —
# ni Bash ni Edit. Cette veille-ci ne peut pas : mesurer un modele exige
# de lancer `ollama`, `nvidia-smi` et des scripts Python, et documenter
# exige d'ecrire dans ROADMAP.md.
#
# La compensation n'est PAS de faire confiance a l'instruction. Les
# proprietes qui comptent sont garanties MECANIQUEMENT par ce script,
# apres coup, exactement comme le renommage en _DONE n'est jamais confie
# au modele :
#
#   G1. config.py est empreinte ET sauvegardee avant la passe. S'il a
#       bouge, il est RESTAURE et l'alerte est journalisee. Aucune
#       bascule de modele en production ne peut survivre a la passe,
#       meme si le modele decide le contraire.
#   G2. La liste des modeles Ollama est relevee avant. Tout modele
#       apparu PENDANT la passe est supprime apres. Les candidats ne
#       peuvent pas s'accumuler semaine apres semaine.
#   G3. Godot est verifie avant ET apres. S'il tourne apres la passe,
#       il est arrete et l'alerte est journalisee (voir ci-dessous).
#
# ── ⚠️ GARDE-FOU GODOT, NON NEGOCIABLE ────────────────────────────────
#
# La mesure VRAM de Godot du 05/08 (246 Mo) a exige que Cyril soit
# PHYSIQUEMENT PRESENT : la fenetre est plein ecran, always_on_top, et
# capte TOUS les clics du bureau — window_manager.gd documente que le
# passthrough souris est sans effet mesure (ROADMAP.md §3). Lancee sans
# supervision, elle rendrait la machine inutilisable jusqu'a ce que
# quelqu'un la ferme.
#
# Cette tache ne relance JAMAIS Godot. La derniere mesure connue est
# reutilisee. Si le code de l'avatar a change depuis, la passe le NOTE
# et laisse le point a la prochaine session ou Cyril est present.
# L'empreinte git de Lucas3D/ sert de temoin, et G3 est le filet.

$ErrorActionPreference = "Stop"

$Projet = "C:\OrionAI"
$Log    = Join-Path $Projet "data\logs\veille_modeles.log"
$Config = Join-Path $Projet "config.py"
$Sauve  = Join-Path $env:TEMP "config_avant_veille.py"

function Ecrire($message) {
    Add-Content -Path $Log -Encoding utf8 -Value (
        "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $message)
}

New-Item -ItemType Directory -Force -Path (Split-Path $Log) | Out-Null
Ecrire "=== debut de la veille hebdomadaire ==="

# ── Garde-fou Godot, AVANT ────────────────────────────────────────────
# S'il tourne deja, ce n'est pas cette tache qui l'a lance : Cyril
# l'utilise peut-etre. On ne touche a rien et on note, pour ne pas
# attribuer plus tard a la passe un process qui la precedait.
$godotAvant = @(Get-Process -Name "Godot*" -ErrorAction SilentlyContinue)
if ($godotAvant) {
    Ecrire "Godot tournait DEJA avant la passe (PID $($godotAvant.Id -join ',')) — non touche"
}

# ── G1 : empreinte + sauvegarde de config.py ──────────────────────────
$empreinteAvant = (Get-FileHash $Config).Hash
Copy-Item $Config $Sauve -Force
$modeleAvant = (Select-String -Path $Config -Pattern '^MODEL_NAME\s*=' | Select-Object -First 1).Line
Ecrire "config.py empreinte : $($empreinteAvant.Substring(0,16))…  ($modeleAvant)"

# ── G2 : inventaire Ollama avant ──────────────────────────────────────
$modelesAvant = @(& ollama list 2>$null | Select-Object -Skip 1 |
    ForEach-Object { ($_ -split '\s+')[0] } | Where-Object { $_ })
Ecrire "modeles presents avant : $($modelesAvant.Count)"

# Temoin pour le point Godot : l'avatar a-t-il change depuis la mesure ?
$hashLucas3D = (& git -C $Projet log -1 --format=%H -- Lucas3D 2>$null)

# ── La passe elle-meme ────────────────────────────────────────────────

$instruction = @"
Tu executes la VEILLE HEBDOMADAIRE LLM + VLM de Luca's (regle 12 de
CLAUDE.md). Tu tournes SANS SUPERVISION, declenchee par une tache
planifiee. Cyril n'est pas devant l'ecran.

CE QUE CETTE PASSE DOIT FAIRE
1. Rechercher sur internet les LLM ET VLM recents disponibles sur
   Ollama, adaptes a la config (RTX 5080, 16 Go). Les DEUX familles
   dans la meme passe — jamais l'une sans l'autre.
2. Mesurer REELLEMENT sur cette machine, protocole ROADMAP.md
   §5.39/§5.56 : VRAM avec contexte realiste (pas un modele vide),
   latence au premier token, debit, et regression sur les tests de
   controle existants (guichet, tutoiement).
   Verifie la disponibilite du tag avant de mesurer : `ollama pull`
   TELECHARGE quand le tag existe (17 Go pour gemma4:26b le 05/08), et
   `ollama show` ne teste que le local.
3. NE BASCULE JAMAIS un modele en production. Ne modifie pas config.py,
   sous aucun pretexte, meme si la mesure est excellente. La decision
   appartient a 100 % a Cyril. (Ce point est aussi garanti
   mecaniquement : config.py est restaure apres la passe s'il a bouge.)
4. Supprime tout modele telecharge pour le test. Aucun candidat ne
   doit s'accumuler d'une semaine sur l'autre.
5. Documente la passe dans ROADMAP.md avec la date, MEME si la
   conclusion est "rien ne change" — l'historique des veilles compte
   autant que son resultat.

⚠️ INTERDIT ABSOLU — NE LANCE JAMAIS GODOT.
La fenetre de l'avatar est plein ecran, always_on_top, et capte TOUS
les clics du bureau (window_manager.gd : le passthrough souris est sans
effet mesure). La mesure du 05/08 a exige que Cyril soit physiquement
present. Sans supervision, lancer Godot rendrait la machine
inutilisable.
Reutilise la derniere mesure connue : GODOT = 246 Mo (05/08/2026).
Dernier commit touchant Lucas3D/ au moment de cette passe :
$hashLucas3D
Si ce commit differe de celui cite dans ROADMAP.md §5.56, NOTE que la
mesure Godot est peut-etre perimee et laisse le point pour la prochaine
fois ou Cyril est present. Ne le remesure pas toi-meme.

EN CAS DE BLOCAGE STRUCTUREL OU D'AMBIGUITE DE SECURITE : ne devine
pas. Depose une note claire dans cowork_workspace/reports/ expliquant
le blocage, et attends l'arbitrage de Cyril. C'est une reponse valable,
pas un echec.

Termine par une ligne unique : VEILLE: <une phrase de conclusion>
"@

try {
    $sortie = & claude -p $instruction `
        --permission-mode dontAsk 2>&1 | Out-String
    $code = $LASTEXITCODE
} catch {
    Ecrire "!! ECHEC de l'invocation : $($_.Exception.GetType().Name)"
    $code = -1
    $sortie = ""
}
Ecrire "claude a rendu le code $code"
$conclusion = ($sortie -split "`n" | Where-Object { $_ -match '^VEILLE:' } | Select-Object -Last 1)
if ($conclusion) { Ecrire "conclusion : $($conclusion.Trim())" }

# ── G1 (controle) : config.py a-t-il bouge ? ──────────────────────────
if ((Get-FileHash $Config).Hash -ne $empreinteAvant) {
    $modeleApres = (Select-String -Path $Config -Pattern '^MODEL_NAME\s*=' |
        Select-Object -First 1).Line
    Ecrire "!! ALERTE : config.py a ete MODIFIE pendant la veille"
    Ecrire "!!   avant : $modeleAvant"
    Ecrire "!!   apres : $modeleApres"
    Copy-Item $Sauve $Config -Force
    Ecrire "!!   config.py RESTAURE — aucune bascule ne survit a une veille"
}
Remove-Item $Sauve -Force -ErrorAction SilentlyContinue

# ── G2 (controle) : les candidats ont-ils ete nettoyes ? ──────────────
$modelesApres = @(& ollama list 2>$null | Select-Object -Skip 1 |
    ForEach-Object { ($_ -split '\s+')[0] } | Where-Object { $_ })
$restes = @($modelesApres | Where-Object { $modelesAvant -notcontains $_ })
if ($restes) {
    Ecrire "$($restes.Count) modele(s) laisse(s) par la passe — suppression mecanique"
    foreach ($m in $restes) {
        try { & ollama rm $m 2>&1 | Out-Null; Ecrire "   supprime : $m" }
        catch { Ecrire "   !! echec de suppression : $m" }
    }
} else {
    Ecrire "aucun modele residuel — nettoyage conforme"
}

# ── G3 (controle) : Godot a-t-il ete lance malgre l'interdiction ? ────
$godotApres = @(Get-Process -Name "Godot*" -ErrorAction SilentlyContinue)
$nouveaux = @($godotApres | Where-Object { $godotAvant.Id -notcontains $_.Id })
if ($nouveaux) {
    Ecrire "!! ALERTE : Godot a ete lance pendant une passe NON SUPERVISEE"
    foreach ($p in $nouveaux) {
        try { Stop-Process -Id $p.Id -Force; Ecrire "!!   arrete : PID $($p.Id)" }
        catch { Ecrire "!!   echec de l'arret : PID $($p.Id)" }
    }
}

Ecrire "=== fin de la veille ==="
