# Comprehensive test script for all API endpoints (PowerShell)

param(
    [string]$BaseUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Testing Order/Payment API" -ForegroundColor Cyan
Write-Host "Base URL: $BaseUrl" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$Passed = 0
$Failed = 0

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Method,
        [string]$Url,
        [hashtable]$Headers = @{},
        [string]$Body = $null,
        [int]$ExpectedStatus
    )
    
    Write-Host -NoNewline "Testing $Name... "
    
    try {
        $params = @{
            Uri = $Url
            Method = $Method
            Headers = $Headers
            ErrorAction = "Stop"
        }
        
        if ($Body) {
            $params.Body = $Body
            $params.ContentType = "application/json"
        }
        
        $response = Invoke-RestMethod @params
        $statusCode = 200  # Invoke-RestMethod doesn't return status code directly
        
        # Use Invoke-WebRequest to get status code
        $webResponse = Invoke-WebRequest -Uri $Url -Method $Method -Headers $Headers -Body $Body -ErrorAction SilentlyContinue
        $statusCode = [int]$webResponse.StatusCode
        
        if ($statusCode -eq $ExpectedStatus) {
            Write-Host "✓ PASS" -ForegroundColor Green "(Status: $statusCode)"
            $script:Passed++
            return $true
        } else {
            Write-Host "✗ FAIL" -ForegroundColor Red "(Expected: $ExpectedStatus, Got: $statusCode)"
            $script:Failed++
            return $false
        }
    } catch {
        $statusCode = 0
        if ($_.Exception.Response) {
            $statusCode = [int]$_.Exception.Response.StatusCode.value__
        }
        
        if ($statusCode -eq $ExpectedStatus) {
            Write-Host "✓ PASS" -ForegroundColor Green "(Status: $statusCode)"
            $script:Passed++
            return $true
        } else {
            Write-Host "✗ FAIL" -ForegroundColor Red "(Expected: $ExpectedStatus, Got: $statusCode)"
            Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
            $script:Failed++
            return $false
        }
    }
}

# Test 1: Root endpoint
Write-Host "1. Root endpoint" -ForegroundColor Yellow
Test-Endpoint -Name "GET /" -Method "GET" -Url "$BaseUrl/" -ExpectedStatus 200
Write-Host ""

# Test 2: Get products
Write-Host "2. GET /products" -ForegroundColor Yellow
$products = Invoke-RestMethod -Uri "$BaseUrl/products" -Method GET
Write-Host "   Products: $($products.products.Count) items"
Test-Endpoint -Name "GET /products" -Method "GET" -Url "$BaseUrl/products" -ExpectedStatus 200
Write-Host ""

# Test 3: Create order (missing key) → 422
Write-Host "3. POST /orders (missing Idempotency-Key)" -ForegroundColor Yellow
try {
    Invoke-RestMethod -Uri "$BaseUrl/orders" -Method POST -Body '{"customerId":"c123","items":[{"productId":"p1","qty":1}]}' -ContentType "application/json" -ErrorAction Stop
    Write-Host "✗ FAIL" -ForegroundColor Red "(Should have failed)"
    $Failed++
} catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 422) {
        Write-Host "✓ PASS" -ForegroundColor Green "(Status: 422)"
        $Passed++
    } else {
        Write-Host "✗ FAIL" -ForegroundColor Red "(Expected: 422)"
        $Failed++
    }
}
Write-Host ""

# Test 4: Create order (first call) → 201
Write-Host "4. POST /orders (first call)" -ForegroundColor Yellow
$key1 = "test-key-$(Get-Date -Format 'yyyyMMddHHmmss')"
$body = '{"customerId":"c123","items":[{"productId":"p1","qty":2},{"productId":"p2","qty":1}]}'
$headers = @{
    "Content-Type" = "application/json"
    "Idempotency-Key" = $key1
}

try {
    $orderResponse = Invoke-RestMethod -Uri "$BaseUrl/orders" -Method POST -Headers $headers -Body $body
    $webResponse = Invoke-WebRequest -Uri "$BaseUrl/orders" -Method POST -Headers $headers -Body $body
    if ($webResponse.StatusCode -eq 201) {
        Write-Host "✓ PASS" -ForegroundColor Green "(Status: 201)"
        Write-Host "   Order ID: $($orderResponse.orderId)"
        Write-Host "   Total: $($orderResponse.total)"
        $orderId = $orderResponse.orderId
        $Passed++
    } else {
        Write-Host "✗ FAIL" -ForegroundColor Red "(Expected: 201, Got: $($webResponse.StatusCode))"
        $Failed++
    }
} catch {
    Write-Host "✗ FAIL" -ForegroundColor Red "Error: $($_.Exception.Message)"
    $Failed++
}
Write-Host ""

# Test 5: Create order (same key, same body) → 200 replay
Write-Host "5. POST /orders (same key, same body - replay)" -ForegroundColor Yellow
try {
    $replayResponse = Invoke-RestMethod -Uri "$BaseUrl/orders" -Method POST -Headers $headers -Body $body
    $webResponse = Invoke-WebRequest -Uri "$BaseUrl/orders" -Method POST -Headers $headers -Body $body
    if ($webResponse.StatusCode -eq 200 -and $replayResponse.idempotentReplay -eq $true) {
        Write-Host "✓ PASS" -ForegroundColor Green "(Status: 200, has idempotentReplay)"
        $Passed++
    } else {
        Write-Host "✗ FAIL" -ForegroundColor Red "(Expected: 200 with idempotentReplay)"
        $Failed++
    }
} catch {
    Write-Host "✗ FAIL" -ForegroundColor Red "Error: $($_.Exception.Message)"
    $Failed++
}
Write-Host ""

# Test 6: Create order (same key, different body) → 409
Write-Host "6. POST /orders (same key, different body)" -ForegroundColor Yellow
$key2 = "test-key-conflict-$(Get-Date -Format 'yyyyMMddHHmmss')"
$headers2 = @{
    "Content-Type" = "application/json"
    "Idempotency-Key" = $key2
}

# First call
Invoke-RestMethod -Uri "$BaseUrl/orders" -Method POST -Headers $headers2 -Body '{"customerId":"c123","items":[{"productId":"p1","qty":1}]}' | Out-Null

# Second call with different body
try {
    Invoke-RestMethod -Uri "$BaseUrl/orders" -Method POST -Headers $headers2 -Body '{"customerId":"c999","items":[{"productId":"p2","qty":5}]}' -ErrorAction Stop
    Write-Host "✗ FAIL" -ForegroundColor Red "(Should have failed with 409)"
    $Failed++
} catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 409) {
        Write-Host "✓ PASS" -ForegroundColor Green "(Status: 409 Conflict)"
        $Passed++
    } else {
        Write-Host "✗ FAIL" -ForegroundColor Red "(Expected: 409, Got: $($_.Exception.Response.StatusCode.value__))"
        $Failed++
    }
}
Write-Host ""

# Test 7: Get order
if ($orderId) {
    Write-Host "7. GET /orders/{orderId}" -ForegroundColor Yellow
    try {
        $getOrder = Invoke-RestMethod -Uri "$BaseUrl/orders/$orderId" -Method GET
        Write-Host "✓ PASS" -ForegroundColor Green "(Status: 200)"
        Write-Host "   Order ID: $($getOrder.orderId), Status: $($getOrder.status)"
        $Passed++
    } catch {
        Write-Host "✗ FAIL" -ForegroundColor Red "Error: $($_.Exception.Message)"
        $Failed++
    }
    Write-Host ""
    
    # Test 8: Confirm order
    Write-Host "8. POST /orders/{orderId}/confirm" -ForegroundColor Yellow
    try {
        $confirmResponse = Invoke-RestMethod -Uri "$BaseUrl/orders/$orderId/confirm" -Method POST
        Write-Host "✓ PASS" -ForegroundColor Green "(Status: 200)"
        Write-Host "   Status: $($confirmResponse.status)"
        $Passed++
    } catch {
        Write-Host "✗ FAIL" -ForegroundColor Red "Error: $($_.Exception.Message)"
        $Failed++
    }
    Write-Host ""
    
    # Test 9: Confirm order again (idempotent)
    Write-Host "9. POST /orders/{orderId}/confirm (already confirmed)" -ForegroundColor Yellow
    try {
        $confirmReplay = Invoke-RestMethod -Uri "$BaseUrl/orders/$orderId/confirm" -Method POST
        if ($confirmReplay.idempotentReplay -eq $true) {
            Write-Host "✓ PASS" -ForegroundColor Green "(Status: 200, idempotent)"
            $Passed++
        } else {
            Write-Host "✗ FAIL" -ForegroundColor Red "(Expected idempotentReplay)"
            $Failed++
        }
    } catch {
        Write-Host "✗ FAIL" -ForegroundColor Red "Error: $($_.Exception.Message)"
        $Failed++
    }
    Write-Host ""
}

# Summary
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Test Summary" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Passed: $Passed" -ForegroundColor Green
Write-Host "Failed: $Failed" -ForegroundColor Red
Write-Host "Total: $($Passed + $Failed)"
Write-Host ""

if ($Failed -eq 0) {
    Write-Host "All tests passed! ✓" -ForegroundColor Green
    exit 0
} else {
    Write-Host "Some tests failed ✗" -ForegroundColor Red
    exit 1
}
