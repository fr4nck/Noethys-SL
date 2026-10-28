@echo off
setlocal
cd /d "%~dp0.."
echo NOETHYS QT C18 - SCOLARITE / PRODUITS / PIECES
echo FIXTURE SQLITE TEMPORAIRE 100%% FICTIVE
echo AUCUNE BASE REELLE - AUCUNE ECRITURE METIER
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" tools\qt_c18_native_demo.py --theme light
) else (
    py -3.11 tools\qt_c18_native_demo.py --theme light
)
if errorlevel 1 (
    echo Echec : verifier Python 3.11 et requirements-qt.txt
    pause
)
endlocal
