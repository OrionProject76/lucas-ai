# cowork_request_runner.ps1 — traite les demandes de cowork_workspace/requests/
#
# ── Pourquoi ce script existe (05/08/2026) ────────────────────────────
#
# Le traitement des demandes etait porte par une tache planifiee COWORK
# (22h). Elle ne peut structurellement pas fonctionner : les sessions
# Cowork tournent dans le cloud, sans acces au pont bureau, donc sans
# acces a C:\OrionAI. Ce n'est pas un probleme reseau a depanner, c'est
# une limite du produit.
#
# La vraie solution est de sortir ce traitement de Cowork, pas de le
# forcer. Ce script appelle Claude Code EN LOCAL, sur cette machine, la
# ou les fichiers existent reellement.
#
# ── Trois gardes, dans l'ordre d'importance ───────────────────────────
#
# 1. AUCUNE invocation s'il n'y a rien a traiter. C'est la garde
#    principale : la tache tourne a chaque ouverture de session et tous
#    les soirs, mais Claude Code n'est lance QUE si un fichier attend.
#    Sans demande, ce script lit un dossier et s'arrete — zero token,
#    zero ecriture, zero risque.
#
# 2. OUTILS RESTREINTS. Claude recoit Read/Glob/Grep/Write. Pas de Bash,
#    pas d'Edit : il ne peut donc pas modifier un fichier existant par
#    l'outil d'edition, ni lancer une commande.
#
# 3. RENOMMAGE FAIT PAR CE SCRIPT, jamais par Claude. Le passage en
#    _DONE est mecanique et verifiable ; le confier au modele
#    l'exposerait a etre oublie ou applique a tort.
#
# Et un controle apres coup : les 4 documents de reference sont
# empreintes AVANT et APRES. Toute modification est signalee dans le log
# — le protocole les declare en lecture seule (requests/README.md).

$ErrorActionPreference = "Stop"

$Projet   = "C:\OrionAI"
$Demandes = Join-Path $Projet "cowork_workspace\requests"
$Rapports = Join-Path $Projet "cowork_workspace\reports"
$Log      = Join-Path $Projet "data\logs\cowork_requests.log"

# Documents declares en lecture seule par le protocole.
$Proteges = @("ROADMAP.md", "CLAUDE.md", "IDEAS.md", "VISION_LONG_TERME.md")

function Ecrire($message) {
    $ligne = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $message
    Add-Content -Path $Log -Value $ligne -Encoding utf8
}

New-Item -ItemType Directory -Force -Path (Split-Path $Log) | Out-Null
New-Item -ItemType Directory -Force -Path $Rapports | Out-Null

# ── Garde 1 : y a-t-il seulement quelque chose a faire ? ──────────────

if (-not (Test-Path $Demandes)) {
    Ecrire "dossier requests/ absent — rien a faire"
    exit 0
}

$enAttente = Get-ChildItem -Path $Demandes -Filter "*.md" -File |
    Where-Object { $_.BaseName -ne "README" -and $_.BaseName -notlike "*_DONE" }

if (-not $enAttente) {
    Ecrire "aucune demande en attente"
    exit 0
}

Ecrire "$($enAttente.Count) demande(s) en attente"

# Empreintes AVANT, pour le controle de lecture seule.
$avant = @{}
foreach ($doc in $Proteges) {
    $chemin = Join-Path $Projet $doc
    if (Test-Path $chemin) { $avant[$doc] = (Get-FileHash $chemin).Hash }
}

# ── Traitement, une demande a la fois ─────────────────────────────────

foreach ($demande in $enAttente) {
    Ecrire "--- traitement : $($demande.Name)"

    $instruction = @"
Tu traites UNE demande deposee dans cowork_workspace/requests/.

Fichier a traiter : cowork_workspace/requests/$($demande.Name)

Protocole (voir cowork_workspace/requests/README.md) :
1. Lis ce fichier de demande.
2. Execute la tache decrite. Tu peux LIRE ROADMAP.md, CLAUDE.md,
   IDEAS.md, VISION_LONG_TERME.md et le code du projet.
3. Depose le resultat dans cowork_workspace/reports/ sous un nom
   explicite se terminant par la date du jour.

INTERDIT, sans exception :
- modifier ROADMAP.md, CLAUDE.md, IDEAS.md ou VISION_LONG_TERME.md
- modifier le moindre fichier de code
- modifier le fichier de demande lui-meme (le renommage est fait
  ailleurs, mecaniquement)

Si la demande est ambigue, ou si l'executer exigerait de modifier un
fichier protege : n'execute rien, et depose a la place dans reports/ une
note expliquant pourquoi. C'est une reponse valable, pas un echec.

Termine par une ligne unique : RAPPORT: <nom du fichier depose>
"@

    $avantRapports = (Get-ChildItem $Rapports -File).Name

    try {
        $sortie = & claude -p $instruction `
            --allowedTools "Read" "Glob" "Grep" "Write" `
            --disallowedTools "Bash" "Edit" "NotebookEdit" `
            --permission-mode dontAsk 2>&1 | Out-String
        $code = $LASTEXITCODE
    } catch {
        Ecrire "    ECHEC de l'invocation : $($_.Exception.GetType().Name)"
        continue
    }

    if ($code -ne 0) {
        Ecrire "    claude a rendu le code $code — demande NON marquee traitee"
        continue
    }

    $nouveaux = (Get-ChildItem $Rapports -File).Name | Where-Object { $avantRapports -notcontains $_ }

    if (-not $nouveaux) {
        # Aucun rapport produit : on ne marque PAS la demande traitee,
        # sinon elle disparaitrait du radar sans avoir rien produit.
        Ecrire "    aucun rapport depose — demande laissee en attente"
        Ecrire "    sortie : $(($sortie -replace '\s+', ' ').Trim() -replace '^(.{0,300}).*$', '$1')"
        continue
    }

    foreach ($n in $nouveaux) { Ecrire "    rapport depose : $n" }

    # Garde 3 : le renommage est mecanique, jamais confie au modele.
    $cible = Join-Path $Demandes ($demande.BaseName + "_DONE" + $demande.Extension)
    Rename-Item -Path $demande.FullName -NewName (Split-Path $cible -Leaf)
    Ecrire "    demande marquee : $(Split-Path $cible -Leaf)"
}

# ── Controle apres coup : les documents proteges ont-ils bouge ? ──────

foreach ($doc in $Proteges) {
    $chemin = Join-Path $Projet $doc
    if (-not (Test-Path $chemin)) { continue }
    if ($avant.ContainsKey($doc) -and (Get-FileHash $chemin).Hash -ne $avant[$doc]) {
        Ecrire "!! ALERTE : $doc a ete MODIFIE alors qu'il est declare en lecture seule"
    }
}

Ecrire "fin du traitement"
