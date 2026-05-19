@echo off
setlocal
cd /d "%~dp0"

set "APP_PYTHONW=%~dp0runtime\python\pythonw.exe"
set "APP_PYTHON=%~dp0runtime\python\python.exe"
set "VENV_PYTHONW=%LOCALAPPDATA%\VozaraApp\.venv\Scripts\pythonw.exe"
set "TCL_LIBRARY=%~dp0runtime\python\tcl\tcl8.6"
set "TK_LIBRARY=%~dp0runtime\python\tcl\tk8.6"

if exist "%VENV_PYTHONW%" (
    start "" "%VENV_PYTHONW%" "%~dp0app.py"
    exit /b 0
)

if exist "%APP_PYTHONW%" (
    "%APP_PYTHON%" "%~dp0main.py"
    exit /b 0
)

pythonw --version >nul 2>&1
if not errorlevel 1 (
    start "" pythonw "%~dp0main.py"
    exit /b 0
)

msg * "Python interno do aplicativo nao foi encontrado. Reinstale usando o instalador oficial atualizado."
exit /b 1
