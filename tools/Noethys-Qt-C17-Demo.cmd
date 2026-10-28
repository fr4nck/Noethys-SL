@echo off
setlocal
cd /d "%~dp0.."
echo =====================================================
echo NOETHYS QT C17 : PILOTAGE SUR DONNEES FICTIVES
echo MOTEUR PARTAGE / ACTIVITES / PLANNING / TARIFS / ETATS
echo AUCUNE BASE REELLE - AUCUNE ECRITURE METIER
echo =====================================================
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" tools\qt_c17_native_demo.py --theme light
) else (
  py -3.11 tools\qt_c17_native_demo.py --theme light
)
if errorlevel 1 (
  echo Impossible de lancer la demonstration C17.
  echo Installer les dependances de requirements-qt.txt.
  pause
)
endlocal
