@echo off
setlocal
cd /d "%~dp0.."
echo =====================================================
echo NOETHYS QT C19 - DEMONSTRATION STRICTEMENT FICTIVE
echo COMPTABILITE / BUDGETS / ENCAISSEMENTS / ORGANISMES
echo DONNEES INVENTEES - AUCUNE ECRITURE METIER
echo =====================================================
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" tools\qt_c19_native_demo.py --theme light
) else (
  py -3.11 tools\qt_c19_native_demo.py --theme light
)
if errorlevel 1 (
  echo Demonstration indisponible. Verifier Python 3.11 et requirements-qt.txt.
  pause
)
endlocal
