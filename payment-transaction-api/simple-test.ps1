# Simple API Flow Test

Write-Host "=== Payment API Flow Test ===" -ForegroundColor Cyan
Write-Host ""

# Test 1: Get products
Write-Host "Test 1: GET /products" -ForegroundColor Yellow
curl http://localhost:8000/products
Write-Host ""

# Test 2: Create order (first time)
Write-Host "Test 2: POST /orders (first time)" -ForegroundColor Yellow
$key = "simple-test-$(Get-Date -Format 'HHmmss')"
Write-Host "Using key: $key"

$headers = @{
    "Content-Type" = "application/json"
    "Idempotency-Key" = $key
}
$bodyObj = @{
    customerId = "c123"
    items = @(
        @{productId = "p1"; qty = 2}
        @{productId = "p2"; qty = 1}
    )
}

try {
    $result1 = Invoke-RestMethod -Uri http://localhost:8000/orders -Method POST -Headers $headers -Body ($bodyObj | ConvertTo-Json) -StatusCodeVariable sc1
    Write-Host "Status: $sc1" -ForegroundColor Green
    Write-Host "Response:" -ForegroundColor Green
    $result1 | ConvertTo-Json
    $orderId = $result1.orderId
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# Test 3: Create same order again (idempotent replay)
Write-Host "Test 3: POST /orders (same key - replay)" -ForegroundColor Yellow

try {
    $result2 = Invoke-RestMethod -Uri http://localhost:8000/orders -Method POST -Headers $headers -Body ($bodyObj | ConvertTo-Json) -StatusCodeVariable sc2
    Write-Host "Status: $sc2" -ForegroundColor Green
    Write-Host "Response:" -ForegroundColor Green
    $result2 | ConvertTo-Json
    
    if ($result2.idempotentReplay -eq $true) {
        Write-Host "✓ Idempotency working!" -ForegroundColor Green
    }
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# Test 4: Get order
if ($orderId) {
    Write-Host "Test 4: GET /orders/$orderId" -ForegroundColor Yellow
    try {
        $getResult = Invoke-RestMethod -Uri "http://localhost:8000/orders/$orderId" -Method GET
        $getResult | ConvertTo-Json
    } catch {
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    }
    Write-Host ""
    
    # Test 5: Confirm order
    Write-Host "Test 5: POST /orders/$orderId/confirm" -ForegroundColor Yellow
    try {
        $confirmResult = Invoke-RestMethod -Uri "http://localhost:8000/orders/$orderId/confirm" -Method POST
        $confirmResult | ConvertTo-Json
    } catch {
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    }
    Write-Host ""
}

Write-Host "=== Test Complete ===" -ForegroundColor Green
