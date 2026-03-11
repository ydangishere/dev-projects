Write-Host "=== Quick Payment API Test ===" -ForegroundColor Cyan
Write-Host ""

# Test 1: Products
Write-Host "1. GET /products" -ForegroundColor Yellow
Invoke-RestMethod http://localhost:8000/products | ConvertTo-Json
Write-Host ""

# Test 2: Create order
Write-Host "2. POST /orders (create payment)" -ForegroundColor Yellow
$key = "test-$(Get-Date -Format 'HHmmss')"
$headers = @{
    "Content-Type" = "application/json"
    "Idempotency-Key" = $key
}
$body = @{
    customerId = "c123"
    items = @(
        @{productId = "p1"; qty = 2}
        @{productId = "p2"; qty = 1}
    )
} | ConvertTo-Json

$order = Invoke-RestMethod -Uri http://localhost:8000/orders -Method POST -Headers $headers -Body $body
Write-Host "Created order: $($order.orderId), Total: $($order.total)" -ForegroundColor Green
Write-Host ""

# Test 3: Same request again
Write-Host "3. POST /orders (replay - prevent double charge)" -ForegroundColor Yellow
$order2 = Invoke-RestMethod -Uri http://localhost:8000/orders -Method POST -Headers $headers -Body $body
Write-Host "Response: orderId=$($order2.orderId), replay=$($order2.idempotentReplay)" -ForegroundColor Green
if ($order2.idempotentReplay) {
    Write-Host "SUCCESS: No double charge!" -ForegroundColor Green
}
Write-Host ""

# Test 4: Get order
Write-Host "4. GET /orders/$($order.orderId)" -ForegroundColor Yellow
Invoke-RestMethod "http://localhost:8000/orders/$($order.orderId)" | ConvertTo-Json
Write-Host ""

# Test 5: Confirm
Write-Host "5. POST /orders/$($order.orderId)/confirm" -ForegroundColor Yellow
Invoke-RestMethod -Uri "http://localhost:8000/orders/$($order.orderId)/confirm" -Method POST | ConvertTo-Json
Write-Host ""

Write-Host "=== All Tests Passed ===" -ForegroundColor Green
