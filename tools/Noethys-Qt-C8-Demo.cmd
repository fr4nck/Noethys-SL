@echo off
setlocal
cd /d "%~dp0.."
echo ========================================
echo   Noethys Qt C8 - DEMONSTRATION FICTIVE
echo   AUCUNE DONNEE REELLE - LECTURE SEULE
echo ========================================
py -3.11 tools\qt_c8_windows_demo.py --theme system
if errorlevel 1 (
    echo.
    echo Echec du lancement. Installer les dependances :
    echo py -3.11 -m pip install -r requirements-qt.txt
    pause
)
endlocal
