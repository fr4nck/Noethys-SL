@echo off
setlocal
cd /d "%~dp0.."
echo =====================================================
echo NOETHYS QT C15 - CONSULTATION 100%% FICTIVE
echo ECHEANCES / ATTESTATIONS / PARAMETRES / EFFECTIFS BRUTS
echo AUCUNE DONNEE REELLE - AUCUNE ECRITURE METIER
echo =====================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" tools\qt_c15_native_modules_demo.py --theme light
) else (
    py -3.11 tools\qt_c15_native_modules_demo.py --theme light
)
if errorlevel 1 (
    echo Lancement impossible. Verifier Python 3.11 et requirements-qt.txt.
    pause
)
endlocal
