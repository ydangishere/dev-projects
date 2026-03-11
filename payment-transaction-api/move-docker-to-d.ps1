# Script: Move Docker data to D:\ drive
# Run this AFTER restarting your computer

Write-Host "=== Moving Docker Data to D:\ ===" -ForegroundColor Cyan
Write-Host ""

# Check if Docker Desktop is running
$dockerProcess = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
if (-not $dockerProcess) {
    Write-Host "Starting Docker Desktop..." -ForegroundColor Yellow
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    Write-Host "Waiting for Docker Desktop to start (30 seconds)..." -ForegroundColor Yellow
    Start-Sleep -Seconds 30
}

Write-Host ""
Write-Host "MANUAL STEPS TO MOVE DATA:" -ForegroundColor Green
Write-Host "1. Open Docker Desktop (should be running now)" -ForegroundColor White
Write-Host "2. Click Settings icon (gear icon) in top right" -ForegroundColor White
Write-Host "3. Go to: Resources → Advanced" -ForegroundColor White
Write-Host "4. Find 'Disk image location'" -ForegroundColor White
Write-Host "5. Change path to: D:\DockerData" -ForegroundColor White
Write-Host "6. Click 'Apply & Restart'" -ForegroundColor White
Write-Host ""
Write-Host "Docker will automatically move all data to D:\" -ForegroundColor Green
Write-Host ""
Write-Host "After that, C:\ will only use ~500MB (just the app)" -ForegroundColor Yellow
Write-Host "D:\ will have ~2-3GB (all Docker images and containers)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
