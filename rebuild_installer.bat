@echo off
echo ============================================
echo Black Forest Tender Scraper - Installer Rebuild
echo ============================================
echo.

cd /d "%~dp0"

REM --- Try override from environment first ---
if defined ISCC_PATH (
    if exist "%ISCC_PATH%" (
        echo Using ISCC from ISCC_PATH environment variable: %ISCC_PATH%
        set "ISCC_CMD=%ISCC_PATH%"
        goto :run_iscc
    ) else (
        echo ISCC_PATH is defined but file not found: %ISCC_PATH%
        set "ISCC_PATH="
    )
)

REM --- Try to find ISCC.exe on PATH ---
for /f "delims=" %%P in ('where ISCC.exe 2^>nul') do (
    set "ISCC_CMD=%%P"
    goto :found_iscc_on_path
)
:found_iscc_on_path
if defined ISCC_CMD (
    echo Found ISCC.exe on PATH: %ISCC_CMD%
    goto :run_iscc
)

echo ISCC.exe not found on PATH. Checking common install locations...

REM --- Original standard locations fallback ---
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    echo Found Inno Setup 6
    set "ISCC_CMD=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    goto :run_iscc
)
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    echo Found Inno Setup 6 (64-bit)
    set "ISCC_CMD=C:\Program Files\Inno Setup 6\ISCC.exe"
    goto :run_iscc
)
if exist "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" (
    echo Found Inno Setup 5
    set "ISCC_CMD=C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
    goto :run_iscc
)
set "ISCC_CMD="

if defined ISCC_CMD (
    echo Using ISCC: %ISCC_CMD%
    goto :run_iscc
)

echo.
echo ERROR: Inno Setup (ISCC.exe) not found in PATH or standard locations.
echo.
echo Options:
echo 1) Enter the folder path where ISCC.exe is installed (this session only).
echo 2) Add the Inno Setup folder to your user PATH permanently (setx) so shells/IDEs can find it.
echo 3) Cancel and install Inno Setup from: https://jrsoftware.org/isinfo.php
echo.

set /p USERCHOICE="Choose 1, 2 or 3 and press Enter: "

if "%USERCHOICE%"=="1" goto :prompt_folder
if "%USERCHOICE%"=="2" goto :add_to_path
echo Aborting. Please install Inno Setup or set ISCC_PATH environment variable.
exit /b 1

:prompt_folder
set /p INPUT_DIR="Enter full folder path containing ISCC.exe (example: C:\Program Files (x86)\Inno Setup 6): "
if exist "%INPUT_DIR%\ISCC.exe" (
    set "ISCC_CMD=%INPUT_DIR%\ISCC.exe"
    echo Using: %ISCC_CMD% for this session only.
    goto :run_iscc
) else (
    echo File not found at "%INPUT_DIR%\ISCC.exe". Aborting.
    exit /b 1
)

:add_to_path
echo You chose to add Inno Setup folder to your user PATH persistently.
set /p NEWDIR="Enter the folder path to add to PATH (example: C:\Program Files (x86)\Inno Setup 6): "
if not exist "%NEWDIR%\ISCC.exe" (
    echo ISCC.exe not found at "%NEWDIR%\ISCC.exe". Aborting PATH update.
    exit /b 1
)

echo Updating user PATH (setx). NOTE: you must restart your terminal/IDE for changes to take effect.
setx PATH "%PATH%;%NEWDIR%" >nul
if %ERRORLEVEL% EQU 0 (
    echo PATH updated successfully.
    echo You can either restart your shell/IDE or set ISCC_PATH for current session now.
    set /p DOSET="Do you want to set ISCC_PATH for this session now? (Y/N): "
    if /I "%DOSET%"=="Y" (
        set "ISCC_PATH=%NEWDIR%\ISCC.exe"
        set "ISCC_CMD=%ISCC_PATH%"
        echo ISCC_PATH set for current session: %ISCC_PATH%
        goto :run_iscc
    ) else (
        echo Please restart your shell/IDE and rerun this script when ready.
        exit /b 0
    )
) else (
    echo Failed to update PATH via setx. You may need to run this script as Administrator or update PATH manually.
    echo Manual PATH add example:
    echo    setx PATH "%%PATH%%;%NEWDIR%"
    exit /b 1
)

:run_iscc
if not defined ISCC_CMD (
    echo No ISCC command found. Exiting.
    exit /b 1
)
echo.
echo Rebuilding installer with version 2.1.4...
echo.
"%ISCC_CMD%" setup.iss

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================
    echo SUCCESS: Installer rebuilt successfully!
    echo ============================================
    echo.
    echo New installer created:
    echo installer_output\BlackForest_Tender_Scraper_2.1.4_Setup.exe
    echo.
) else (
    echo.
    echo ============================================
    echo ERROR: Failed to rebuild installer
    echo ============================================
    echo.
    echo Error code: %ERRORLEVEL%
    echo.
)

echo Press any key to exit...
pause >nul

exit /b %ERRORLEVEL%
