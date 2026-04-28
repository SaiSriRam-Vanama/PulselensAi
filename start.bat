@echo off
title Startup Intelligence Dashboard
color 0B

echo.
echo   ╔══════════════════════════════════════════════════╗
echo   ║    Startup Intelligence Dashboard               ║
echo   ║    Website + Hiring + Social + Hybrid AI        ║
echo   ╚══════════════════════════════════════════════════╝
echo.

cd /d "%~dp0backend"

echo   [1/3] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   ERROR: Python not found. Please install Python 3.8+
    pause
    exit /b 1
)
echo   OK  Python found
echo.

echo   [2/3] Checking dependencies...
pip show flask >nul 2>&1
if %errorlevel% neq 0 (
    echo   Installing dependencies (first run only)...
    pip install -r requirements.txt --quiet
)
echo   OK  Dependencies ready
echo.

echo   [3/3] Starting Flask server...
echo.
echo   ╔══════════════════════════════════════════════════╗
echo   ║  Dashboard: http://localhost:5000               ║
echo   ║  Press Ctrl+C to stop the server               ║
echo   ╚══════════════════════════════════════════════════╝
echo.

REM Open browser after 2 second delay
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"

REM Start Flask
python app.py
