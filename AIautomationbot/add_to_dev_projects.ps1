# Add AIautomationbot to dev-projects monorepo
$ErrorActionPreference = "Stop"
$sourceDir = $PSScriptRoot
$parentDir = Split-Path $sourceDir -Parent
$devProjectsDir = Join-Path $parentDir "dev-projects"

Write-Host "1. Cloning dev-projects..."
if (Test-Path $devProjectsDir) {
    Remove-Item -Recurse -Force $devProjectsDir
}
git clone https://github.com/ydangishere/dev-projects.git $devProjectsDir

Write-Host "2. Copying AIautomationbot..."
$targetDir = Join-Path $devProjectsDir "AIautomationbot"
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

$exclude = @("__pycache__", ".git", "tradingview_session.json", "telegram_config.py", "alert_screenshots", ".gitignore")
Get-ChildItem $sourceDir -Force | Where-Object {
    $exclude -notcontains $_.Name
} | ForEach-Object {
    Copy-Item $_.FullName -Destination $targetDir -Recurse -Force
}

# Restore .gitignore (needed for repo)
Copy-Item (Join-Path $sourceDir ".gitignore") -Destination $targetDir -Force

Write-Host "3. Updating dev-projects README..."
$readmePath = Join-Path $devProjectsDir "README.md"
$readme = Get-Content $readmePath -Raw
$newEntry = @"

- **TradingView Alerts to Telegram** (`AIautomationbot`): Python app that opens TradingView, screenshots each alert, and sends them via Telegram.
 - Monorepo folder: [`AIautomationbot`](https://github.com/ydangishere/dev-projects/tree/main/AIautomationbot)
 - Part of dev-projects (no separate repo)
"@

if ($readme -notmatch "AIautomationbot") {
    $insertPos = $readme.IndexOf("Each subfolder")
    $readme = $readme.Insert($insertPos, $newEntry + "`n`n")
    Set-Content $readmePath -Value $readme -NoNewline
}

Write-Host "4. Committing and pushing..."
Set-Location $devProjectsDir
git add AIautomationbot README.md
git config user.email "ydang@users.noreply.github.com"
git config user.name "ydangishere"
git commit -m "Add AIautomationbot: TradingView alerts to Telegram"
git push origin main

Write-Host "Done! AIautomationbot added to dev-projects."
