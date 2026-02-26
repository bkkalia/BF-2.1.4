@echo off
:: Set working directory to the folder containing this script
cd /d "%~dp0"

echo ==============================================
echo    BlackForest Reflex Dashboard Launcher
echo ==============================================
echo.

:: Start with the script's own folder as the default project root
set PROJECT_ROOT=%~dp0
:: Strip trailing backslash for cleaner display
if "%PROJECT_ROOT:~-1%"=="\" set PROJECT_ROOT=%PROJECT_ROOT:~0,-1%

:CHECK_ROOT
echo Project root: %PROJECT_ROOT%
echo.

:: Check for .venv
if not exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
    echo [NOT FOUND] .venv\Scripts\python.exe
    echo.
    set /p PROJECT_ROOT="Enter the correct project root path (e.g. C:\MyProjects\BF 2.1.4): "
    :: Strip any trailing backslash or quotes the user may have typed
    if "%PROJECT_ROOT:~-1%"=="\" set PROJECT_ROOT=%PROJECT_ROOT:~0,-1%
    if "%PROJECT_ROOT:~-1%"==" " set PROJECT_ROOT=%PROJECT_ROOT:~0,-1%
    echo.
    goto CHECK_ROOT
)

:: Check for dashboard directory
if not exist "%PROJECT_ROOT%\tender_dashboard_reflex" (
    echo [NOT FOUND] tender_dashboard_reflex directory
    echo.
    set /p PROJECT_ROOT="Enter the correct project root path (e.g. C:\MyProjects\BF 2.1.4): "
    if "%PROJECT_ROOT:~-1%"=="\" set PROJECT_ROOT=%PROJECT_ROOT:~0,-1%
    if "%PROJECT_ROOT:~-1%"==" " set PROJECT_ROOT=%PROJECT_ROOT:~0,-1%
    echo.
    goto CHECK_ROOT
)

echo [OK] Found project at: %PROJECT_ROOT%
echo [OK] URL: http://localhost:3000
echo.
echo Starting Reflex... (first run may take a minute to compile)
echo Press Ctrl+C to stop.
echo.

cd /d "%PROJECT_ROOT%\tender_dashboard_reflex"
"%PROJECT_ROOT%\.venv\Scripts\python.exe" -m reflex run

echo.
echo Dashboard stopped.
pause