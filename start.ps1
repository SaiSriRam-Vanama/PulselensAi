# Startup Health Analysis Dashboard - Quick Start Script (Auto-Launch)
# Run this script to start the application

$Host.UI.RawUI.WindowTitle = "Startup Intelligence Dashboard"

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║    🚀  Startup Intelligence Dashboard            ║" -ForegroundColor Cyan
Write-Host "  ║    Website + Hiring + Social + Hybrid AI         ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Navigate to backend directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendPath = Join-Path $scriptPath "backend"
Set-Location -Path $backendPath

# ── Step 1: Python check ──────────────────────────────────────────────
Write-Host "  [1/3] Checking Python installation..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "  ✗ Python not found! Please install Python 3.8+" -ForegroundColor Red
    pause
    exit 1
}

# ── Step 2: Install dependencies if needed ────────────────────────────
Write-Host ""
Write-Host "  [2/3] Checking dependencies..." -ForegroundColor Yellow
$pipCheck = pip show flask 2>&1
if ($pipCheck -match "Name: Flask") {
    Write-Host "  ✓ Dependencies already installed" -ForegroundColor Green
} else {
    Write-Host "  Installing dependencies (first run only)..." -ForegroundColor Yellow
    pip install -r requirements.txt --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Failed to install dependencies" -ForegroundColor Red
        pause
        exit 1
    }
}

# ── Step 3: Start server and open browser ─────────────────────────────
Write-Host ""
Write-Host "  [3/3] Starting Flask server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║  Dashboard URL : http://localhost:5000           ║" -ForegroundColor Green
Write-Host "  ║  Press Ctrl+C  : to stop the server             ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

# Open browser after a short delay (let Flask start first)
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:5000"
} | Out-Null

# Start the Flask application (blocking)
python app.py
