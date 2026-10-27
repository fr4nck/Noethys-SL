@echo off
setlocal
cd /d "%~dp0.."
echo ===================================================
echo NOETHYS QT C12 - COQUE PRINCIPALE FICTIVE
echo AUCUNE BASE REELLE - AUCUNE ECRITURE METIER
echo ===================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" tools\qt_c12_native_shell_demo.py --theme light
) else (
    py -3.11 tools\qt_c12_native_shell_demo.py --theme light
)
if errorlevel 1 (
    echo Le lancement a echoue. Verifier Python et requirements-qt.txt.
    pause
)
endlocal
