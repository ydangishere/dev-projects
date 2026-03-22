# Setup videomakerauto - chạy 1 lần sau khi pull/clone
# Usage: .\setup.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "=== videomakerauto Setup ===" -ForegroundColor Cyan

# 1. Cài thư viện
Write-Host "`n[1/2] Installing dependencies..." -ForegroundColor Yellow
Set-Location $ProjectRoot
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit 1 }

# 2. Tạo .env nếu chưa có
if (-not (Test-Path "$ProjectRoot\.env")) {
    Copy-Item "$ProjectRoot\.env.example" "$ProjectRoot\.env"
    Write-Host "`n[2/2] Created .env from .env.example" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "IMPORTANT: Open .env and add your API keys:" -ForegroundColor Red
    Write-Host "  - OPENAI_API_KEY (from platform.openai.com)"
    Write-Host "  - ELEVENLABS_API_KEY (from elevenlabs.io)"
    Write-Host ""
    notepad "$ProjectRoot\.env"
} else {
    Write-Host "`n[2/2] .env already exists, skipping" -ForegroundColor Green
}

Write-Host ""
Write-Host "Done! Run: python main.py `"your topic`"" -ForegroundColor Green
