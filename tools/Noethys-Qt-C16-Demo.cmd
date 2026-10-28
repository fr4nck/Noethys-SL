@echo off
setlocal
cd /d "%~dp0.."
echo ======================================================
echo NOETHYS QT C16 - DEMONSTRATION STRICTEMENT FICTIVE
echo PLANNING / TARIFS / ETATS DES CONSOMMATIONS / BADGEAGE
echo AUCUNE BASE REELLE - AUCUNE ECRITURE METIER
echo ======================================================
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" tools\qt_c16_native_demo.py --theme light
) else (
  py -3.11 tools\qt_c16_native_demo.py --theme light
)
if errorlevel 1 (
  echo Impossible de lancer la demonstration C16.
  echo Installer requirements-qt.txt dans Python 3.11.
  pause
)
endlocal
