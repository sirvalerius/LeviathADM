@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM LeviathADM demo: python\python.exe (embedded) senza venv.  leviathadm.cmd [--porta N]
REM -s: ignora i pacchetti utente (%APPDATA%\Python) di un altro Python 3.12 presente sul PC
if exist python\python.exe (
    python\python.exe -s avvia_demo.py %*
) else (
    echo python\ assente: serve un Python 3.12 con i pacchetti di requirements.txt
    python avvia_demo.py %*
)
if errorlevel 1 pause
