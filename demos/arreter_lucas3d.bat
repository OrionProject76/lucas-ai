@echo off
REM /!\ FINS DE LIGNE CRLF OBLIGATOIRES - NE PAS CONVERTIR EN LF.
REM
REM cmd.exe exige CRLF dans un fichier .bat. Avec des fins de ligne Unix
REM (LF seul), son analyseur mange des caracteres en debut de ligne :
REM `setlocal` devient `tlocal`, `REM` devient `M`, et les branches
REM if/else s'executent TOUTES. Mesure le 07/08/2026 : le script a
REM affiche a la fois "arrete", "ne tournait pas" et "TOUJOURS present",
REM et n'a PAS tue le process.
REM
REM Plus pernicieux encore : une version PLUS COURTE du meme script avait
REM fonctionne quelques minutes plus tot, deja en LF. cmd.exe echoue de
REM facon dependante du contenu et de la taille - le premier succes etait
REM de la CHANCE, pas une preuve. Un filet de securite ne doit jamais en
REM dependre. Voir .gitattributes, qui force CRLF sur *.bat.
setlocal enabledelayedexpansion
REM ============================================================
REM  ARRET D'URGENCE DE LUCAS3D  --  06/08/2026
REM ============================================================
REM
REM  Pourquoi ce fichier existe :
REM  Le 06/08/2026, la fenetre Lucas3D s'est affichee PAR-DESSUS le
REM  Gestionnaire des taches, le rendant inutilisable a la souris.
REM  Seule sortie trouvee : touche Windows, survol de l'icone, clic sur
REM  la croix. Un contournement, pas une solution.
REM
REM  Regle posee par Cyril : le filet de securite ne doit JAMAIS dependre
REM  du bon fonctionnement de ce qu'on est en train de tester.
REM
REM  Ce script ne depend de RIEN cote Lucas3D :
REM    - pas du rendu       (il n'affiche rien)
REM    - pas du focus       (WINDOW_FLAG_NO_FOCUS tue les raccourcis
REM                          internes F10/F11/F12 par construction)
REM    - pas de l'appli vivante (taskkill /F n'attend aucune reponse,
REM                          il fonctionne meme sur un process GELE)
REM
REM  Utilisation : double-clic. C'est tout.
REM
REM  Chemins ABSOLUS vers System32, et non les noms courts : teste le
REM  06/08/2026 depuis un shell dont le PATH exposait les find/timeout
REM  d'Unix (Git Bash). Les outils Windows n'etaient alors PAS ceux
REM  appeles, et la branche de verification est passee par ACCIDENT
REM  (l'erreur Unix mettait ERRORLEVEL a non-nul, ce qui menait par
REM  hasard a la bonne branche). Un script de secours ne doit pas
REM  dependre du PATH de celui qui le lance.
REM ============================================================

set "SYS=%SystemRoot%\System32"

"%SYS%\taskkill.exe" /F /IM Lucas3D.exe >nul 2>&1

if %ERRORLEVEL% EQU 0 (
    echo.
    echo   [OK] Lucas3D a ete arrete.
) else (
    echo.
    echo   [i] Lucas3D ne tournait pas -- rien a arreter.
)

REM Verification reelle : on ne fait pas confiance au code de retour seul.
REM
REM /!\ ATTENDRE AVANT DE VERIFIER - corrige le 07/08/2026.
REM taskkill /F rend la main AVANT que Windows n'ait libere le process.
REM Verifier dans la foulee donnait un FAUX POSITIF : le script annoncait
REM "TOUJOURS present" alors que le process etait bel et bien mort
REM (verifie independamment dans la seconde qui suivait). Une alerte qui
REM crie au loup est pire que pas d'alerte : elle enverrait Cyril ouvrir
REM le Gestionnaire des taches pour rien, precisement au moment ou il a
REM besoin de pouvoir se fier a ce script. Trois essais d'une seconde.
set "RESTE=1"
for /L %%i in (1,1,3) do (
    if "!RESTE!"=="1" (
        "%SYS%\timeout.exe" /t 1 /nobreak >nul 2>&1
        "%SYS%\tasklist.exe" /FI "IMAGENAME eq Lucas3D.exe" 2>nul | "%SYS%\find.exe" /I "Lucas3D.exe" >nul
        if errorlevel 1 set "RESTE=0"
    )
)
if "!RESTE!"=="1" (
    echo   [!!] ATTENTION : un process Lucas3D.exe est TOUJOURS present.
    echo        Ouvrir le Gestionnaire des taches et le tuer a la main.
) else (
    echo   [OK] Verifie : plus aucun process Lucas3D.exe.
)

echo.
REM /nobreak + erreurs etouffees : timeout.exe refuse de tourner quand
REM l'entree standard est redirigee (rencontre en testant depuis
REM PowerShell). C'est une pause de confort, jamais une etape critique —
REM elle ne doit pas pouvoir faire echouer un script de secours.
"%SYS%\timeout.exe" /t 4 /nobreak >nul 2>&1
endlocal
