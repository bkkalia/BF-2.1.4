@echo off
REM Windows Batch File for HP Tenders Department Scraping
REM Use this with Windows Task Scheduler for automated daily scraping

echo ========================================
echo Black Forest Tender Scraper - CLI Mode
echo HP Tenders Department Scraping
echo ========================================
echo.

REM Set the script directory (where this batch file is located)
set "SCRIPT_DIR=%~dp0"

REM Change to the script directory
cd /d "%SCRIPT_DIR%"

REM Set Python executable (adjust if needed)
set "PYTHON_EXE=python"

REM Set default output directory (can be overridden)
set "DEFAULT_OUTPUT=%SCRIPT_DIR%Tender_Downloads"

REM Set log file path
set "LOG_FILE=%SCRIPT_DIR%logs\hp_tenders_%date:~-4,4%%date:~-10,2%%date:~-7,2%.log"

REM Create logs directory if it doesn't exist
if not exist "%SCRIPT_DIR%logs" mkdir "%SCRIPT_DIR%logs"

echo Script Directory: %SCRIPT_DIR%
echo Output Directory: %DEFAULT_OUTPUT%
echo Log File: %LOG_FILE%
echo.

REM Run the department scraping
echo Starting HP Tenders department scraping...
echo.

"%PYTHON_EXE%" main.py department --all --output "%DEFAULT_OUTPUT%" --log "%LOG_FILE%" --verbose

REM Check the exit code
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo SUCCESS: Scraping completed successfully!
    echo ========================================
    echo Output saved to: %DEFAULT_OUTPUT%
    echo Log saved to: %LOG_FILE%
) else (
    echo.
    echo ========================================
    echo ERROR: Scraping failed with exit code %ERRORLEVEL%
    echo ========================================
    echo Check the log file for details: %LOG_FILE%
)

echo.
echo Press any key to exit...
pause >nul

REM Exit with the same error code as the Python script
exit /b %ERRORLEVEL%
