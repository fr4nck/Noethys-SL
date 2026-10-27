@echo off
setlocal
cd /d "%~dp0.."
echo =======================================================
echo NOETHYS QT C13 - MODULES FINANCIERS FICTIFS
echo FACTURATION / REGLEMENTS / TRESORERIE - LECTURE SEULE
echo =======================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" tools\qt_c13_native_finance_demo.py --theme light
) else (
    py -3.11 tools\qt_c13_native_finance_demo.py --theme light
)
if errorlevel 1 (
    echo Lancement impossible. Verifier Python 3.11 et requirements-qt.txt.
    pause
)
endlocal
