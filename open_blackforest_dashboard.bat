@echo off
cd /d "%~dp0"

set PROJECT_ROOT=%~dp0
if "%PROJECT_ROOT:~-1%"=="\" set PROJECT_ROOT=%PROJECT_ROOT:~0,-1%

set RUNTIME_FILE=%PROJECT_ROOT%\dashboard_runtime.env
set APP_URL=
set START_SCRIPT=%PROJECT_ROOT%\start_reflex_dashboard.bat

if exist "%RUNTIME_FILE%" (
    for /f "tokens=1,* delims==" %%A in (%RUNTIME_FILE%) do (
        if /I "%%A"=="APP_URL" set APP_URL=%%B
    )
)

if "%APP_URL%"=="" set APP_URL=http://blackforest-dashboard.localhost:3000

call :CHECK_URL "%APP_URL%"
if "%URL_OK%"=="1" goto OPEN_URL

echo Dashboard not reachable at: %APP_URL%
if not exist "%START_SCRIPT%" (
    echo [ERROR] Launcher not found: %START_SCRIPT%
    goto :eof
)

echo Starting dashboard launcher...
start "BlackForest Dashboard Launcher" cmd /c ""%START_SCRIPT%""

set /a RETRIES=45
:WAIT_LOOP
call :READ_APP_URL
call :CHECK_URL "%APP_URL%"
if "%URL_OK%"=="1" goto OPEN_URL
set /a RETRIES-=1
if %RETRIES% LEQ 0 (
    echo [WARN] Dashboard did not become reachable in time.
    echo [INFO] You can manually open later at: %APP_URL%
    goto :eof
)
timeout /t 2 /nobreak >nul
goto WAIT_LOOP

:OPEN_URL
echo Opening Dashboard: %APP_URL%
start "" "%APP_URL%"
goto :eof

:READ_APP_URL
if exist "%RUNTIME_FILE%" (
    for /f "tokens=1,* delims==" %%A in (%RUNTIME_FILE%) do (
        if /I "%%A"=="APP_URL" set APP_URL=%%B
    )
)
if "%APP_URL%"=="" set APP_URL=http://blackforest-dashboard.localhost:3000
goto :eof

:CHECK_URL
set URL_OK=0
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '%~1' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } else { exit 1 } } catch { exit 1 }"
if not errorlevel 1 set URL_OK=1
goto :eof
