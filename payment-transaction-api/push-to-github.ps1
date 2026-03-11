# Push to GitHub Script

Write-Host "=== Push Payment API to GitHub ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Initialize Git
Write-Host "Step 1: Initializing Git repository..." -ForegroundColor Yellow
git init
Write-Host ""

# Step 2: Add all files
Write-Host "Step 2: Adding all files..." -ForegroundColor Yellow
git add .
Write-Host ""

# Step 3: Commit
Write-Host "Step 3: Creating commit..." -ForegroundColor Yellow
git commit -m "Initial commit: Payment Transaction API with idempotency and concurrency handling"
Write-Host ""

# Step 4: Get GitHub repo URL
Write-Host "Step 4: Enter your GitHub repository URL" -ForegroundColor Yellow
Write-Host "Example: https://github.com/yourusername/payment-api.git" -ForegroundColor Gray
$repoUrl = Read-Host "GitHub URL"

if ($repoUrl) {
    Write-Host ""
    Write-Host "Step 5: Adding remote and pushing..." -ForegroundColor Yellow
    git branch -M main
    git remote add origin $repoUrl
    git push -u origin main
    Write-Host ""
    Write-Host "SUCCESS! Code pushed to GitHub!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "No URL provided. Manual push:" -ForegroundColor Yellow
    Write-Host "git remote add origin <your-github-url>" -ForegroundColor White
    Write-Host "git branch -M main" -ForegroundColor White
    Write-Host "git push -u origin main" -ForegroundColor White
}

Write-Host ""
Write-Host "=== Complete ===" -ForegroundColor Cyan
