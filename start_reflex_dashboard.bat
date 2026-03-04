@echo off
:: Set working directory to the folder containing this script
cd /d "%~dp0"

echo ==============================================
echo    BlackForest Reflex Dashboard Launcher
echo ==============================================
echo.

set FRONTEND_START=3000
set BACKEND_START=8600
set APP_HOST=blackforest-dashboard.localhost
set RUNTIME_FILE=dashboard_runtime.env

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

call :FIND_FREE_PORT %FRONTEND_START% FRONTEND_PORT
call :FIND_FREE_PORT %BACKEND_START% BACKEND_PORT

if "%FRONTEND_PORT%"=="" (
    echo [ERROR] Could not find a free frontend port near %FRONTEND_START%
    goto END
)

if "%BACKEND_PORT%"=="" (
    echo [ERROR] Could not find a free backend port near %BACKEND_START%
    goto END
)

if /I "%FRONTEND_PORT%"=="%BACKEND_PORT%" (
    set /a BACKEND_START=%BACKEND_PORT%+1
    call :FIND_FREE_PORT %BACKEND_START% BACKEND_PORT
)

if not "%FRONTEND_PORT%"=="%FRONTEND_START%" (
    echo [INFO] Frontend port %FRONTEND_START% is busy. Using %FRONTEND_PORT%.
)
if not "%BACKEND_PORT%"=="%BACKEND_START%" (
    echo [INFO] Backend port %BACKEND_START% is busy. Using %BACKEND_PORT%.
)

set APP_URL=http://%APP_HOST%:%FRONTEND_PORT%
set BACKEND_URL=http://localhost:%BACKEND_PORT%

(
    echo APP_HOST=%APP_HOST%
    echo FRONTEND_PORT=%FRONTEND_PORT%
    echo BACKEND_PORT=%BACKEND_PORT%
    echo APP_URL=%APP_URL%
    echo BACKEND_URL=%BACKEND_URL%
) > "%PROJECT_ROOT%\%RUNTIME_FILE%"

echo [OK] Name: %APP_HOST%
echo [OK] URL: %APP_URL%
echo [OK] Backend: http://localhost:%BACKEND_PORT%
echo [OK] Runtime file: %PROJECT_ROOT%\%RUNTIME_FILE%
echo.
echo Starting Reflex... (first run may take a minute to compile)
echo Press Ctrl+C to stop.
echo.

cd /d "%PROJECT_ROOT%\tender_dashboard_reflex"
"%PROJECT_ROOT%\.venv\Scripts\python.exe" -m reflex run --frontend-port %FRONTEND_PORT% --backend-port %BACKEND_PORT%

echo.
echo Dashboard stopped.
pause

goto :eof

:FIND_FREE_PORT
setlocal EnableDelayedExpansion
set "START_PORT=%~1"
set "FOUND_PORT="

for /f %%P in ('powershell -NoProfile -Command "$start=[int]'%~1'; for($p=$start; $p -lt ($start+500); $p++){ if(-not (Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue)){ Write-Output $p; break } }"') do (
    set "FOUND_PORT=%%P"
)

endlocal & set "%~2=%FOUND_PORT%"
goto :eof

:END
echo.
echo Launcher aborted.
pause