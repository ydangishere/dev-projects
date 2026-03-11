# Install WSL (Windows Subsystem for Linux)
# Required for Docker Desktop

Write-Host "=== Installing WSL ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "This will:" -ForegroundColor Yellow
Write-Host "1. Enable WSL feature on Windows" -ForegroundColor White
Write-Host "2. Download Ubuntu (default Linux distro)" -ForegroundColor White
Write-Host "3. Install WSL 2 kernel" -ForegroundColor White
Write-Host ""
Write-Host "Time: ~5-10 minutes" -ForegroundColor Yellow
Write-Host "Size: ~500MB download" -ForegroundColor Yellow
Write-Host ""

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script must run as Administrator!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Right-click this file → 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

Write-Host "Installing WSL..." -ForegroundColor Green
wsl --install

Write-Host ""
Write-Host "=== Installation Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "IMPORTANT: You must restart your computer!" -ForegroundColor Yellow
Write-Host ""
Write-Host "After restart:" -ForegroundColor Cyan
Write-Host "1. Docker Desktop will work properly" -ForegroundColor White
Write-Host "2. Run: .\move-docker-to-d.ps1 (to move data to D:\)" -ForegroundColor White
Write-Host "3. Run: docker compose up --build (to test project)" -ForegroundColor White
Write-Host ""
pause
