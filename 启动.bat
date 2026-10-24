@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

rem If the service is already running, just open the dashboard.
netstat -ano | findstr /R /C:":8787 " | findstr /C:"LISTENING" >nul
if not errorlevel 1 (
    echo OCS Bank is already running on port 8787.
    start "" "http://127.0.0.1:8787"
    exit /b 0
)

set "PY="
py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 set "PY=py -3"

if not defined PY (
    python -c "import sys" >nul 2>nul
    if not errorlevel 1 set "PY=python"
)

if not defined PY (
    echo.
    echo [ERROR] A working Python 3 was not found.
    echo The "python" command may be the Microsoft Store placeholder.
    echo Install Python 3.10+ from https://www.python.org/downloads/
    echo and check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo Starting OCS Bank with %PY% ...
%PY% app.py
set "CODE=%errorlevel%"

if not "%CODE%"=="0" (
    echo.
    echo [ERROR] Service exited with code %CODE%.
    echo If port 8787 is already in use, double-click the stop script first.
    echo.
    pause
)
