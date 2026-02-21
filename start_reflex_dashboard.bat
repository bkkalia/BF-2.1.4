@echo off
echo ==============================================
echo    BlackForest Reflex Dashboard Launcher
echo ==============================================
echo.
echo This script will start the Reflex dashboard.
echo The dashboard will be available at:
echo http://localhost:3000
echo.
echo Press any key to continue...
pause >nul

echo.
echo 1. Checking project directory...
if not exist "tender_dashboard_reflex" (
    echo Error: Cannot find tender_dashboard_reflex directory
    echo Please run this script from the BF 2.1.4 project root
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

echo 2. Activating virtual environment...
if not exist ".venv\Scripts\activate.bat" (
    echo Error: Cannot find virtual environment
    echo Please ensure the .venv folder exists
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

call .venv\Scripts\activate.bat

echo 3. Navigating to dashboard directory...
cd tender_dashboard_reflex

echo 4. Starting Reflex dashboard...
echo.
echo The dashboard is starting. This may take a few minutes...
echo.
echo Once running, the dashboard will be available at:
echo http://localhost:3000
echo.
echo To stop the dashboard, press Ctrl+C
echo.

python -m reflex run

echo.
echo Dashboard stopped.
echo Press any key to exit...
pause >nul