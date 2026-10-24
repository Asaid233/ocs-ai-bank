@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
set "PORT=8787"
set "FOUND=0"

for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":%PORT% " ^| findstr /C:"LISTENING"') do (
    set "PID=%%a"
    if not "!PID!"=="0" (
        set "FOUND=1"
        echo Stopping service on port %PORT% ^(PID !PID!^) ...
        taskkill /F /PID !PID! >nul 2>nul
    )
)

if "%FOUND%"=="0" (
    echo No service is listening on port %PORT%.
) else (
    echo Done. Port %PORT% is free.
)
echo.
pause
