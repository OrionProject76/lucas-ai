@echo off
REM Ouvre l'apercu du bureau 3D avec un petit serveur local.
REM --bind 127.0.0.1 : le dossier n'est JAMAIS expose sur le reseau,
REM seul ce PC peut y acceder. Ferme cette fenetre pour arreter le serveur.

cd /d "%~dp0"
echo.
echo   Bureau 3D Luca's - apercu des themes
echo   Serveur local sur http://127.0.0.1:8777  (ce PC uniquement)
echo   Ferme cette fenetre pour l'arreter.
echo.
start "" http://127.0.0.1:8777/bureau3d.html
python -m http.server 8777 --bind 127.0.0.1
