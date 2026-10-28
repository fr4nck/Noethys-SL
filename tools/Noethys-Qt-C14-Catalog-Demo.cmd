@echo off
setlocal
cd /d "%~dp0.."
echo =======================================================
echo NOETHYS QT C14 - SIX GRANDS MODULES ADMINISTRATIFS
echo COTISATIONS / CONTRATS / QUOTIENTS / LOCATIONS
echo COMMANDES / DEVIS - BASE FICTIVE / LECTURE SEULE
echo =======================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" tools\qt_c14_native_catalog_demo.py --theme light
) else (
    py -3.11 tools\qt_c14_native_catalog_demo.py --theme light
)
if errorlevel 1 (
    echo Lancement impossible. Verifier Python 3.11 et requirements-qt.txt.
    pause
)
endlocal
