# Test Concurrency Script for Order API
# Usage: .\test_concurrency.ps1 [base_url]

param(
    [string]$BaseUrl = "http://localhost:8000"
)

Write-Host "=== Order API Concurrency Test ===" -ForegroundColor Cyan
Write-Host "Base URL: $BaseUrl" -ForegroundColor Yellow
Write-Host ""

# Generate unique key
$key = "concurrent-test-$(Get-Date -Format 'yyyyMMddHHmmss')"
Write-Host "Using Idempotency-Key: $key" -ForegroundColor Green
Write-Host ""

# Prepare request
$url = "$BaseUrl/orders"
$body = @{
    customerId = "c123"
    items = @(
        @{ productId = "p1"; qty = 2 }
        @{ productId = "p2"; qty = 1 }
    )
} | ConvertTo-Json -Compress

$headers = @{
    "Content-Type" = "application/json"
    "Idempotency-Key" = $key
}

Write-Host "Sending 10 concurrent requests..." -ForegroundColor Yellow

# Measure time
$startTime = Get-Date

# Send 10 concurrent requests
$jobs = 1..10 | ForEach-Object {
    Start-Job -ScriptBlock {
        param($url, $body, $headers)
        try {
            $response = Invoke-RestMethod -Uri $url -Method POST -Body $body -Headers $headers -ErrorAction Stop
            return @{
                Success = $true
                OrderId = $response.orderId
                Status = $response.status
                Total = $response.total
                IdempotentReplay = $response.idempotentReplay
            }
        } catch {
            return @{
                Success = $false
                Error = $_.Exception.Message
                StatusCode = $_.Exception.Response.StatusCode.value__
            }
        }
    } -ArgumentList $url, $body, ($headers | ConvertTo-Json)
}

# Wait for all jobs to complete
Write-Host "Waiting for responses..." -ForegroundColor Yellow
$results = $jobs | Wait-Job | Receive-Job
$jobs | Remove-Job

$endTime = Get-Date
$duration = ($endTime - $startTime).TotalSeconds

# Analyze results
Write-Host ""
Write-Host "=== Results ===" -ForegroundColor Cyan
Write-Host "Total requests: $($results.Count)" -ForegroundColor White
Write-Host "Duration: $([math]::Round($duration, 2)) seconds" -ForegroundColor White
Write-Host ""

$successful = $results | Where-Object { $_.Success -eq $true }
$failed = $results | Where-Object { $_.Success -eq $false }

if ($successful) {
    $uniqueOrderIds = ($successful | Select-Object -ExpandProperty OrderId -Unique)
    $replayCount = ($successful | Where-Object { $_.IdempotentReplay -eq $true }).Count
    
    Write-Host "Successful requests: $($successful.Count)" -ForegroundColor Green
    Write-Host "Unique orderIds created: $($uniqueOrderIds.Count)" -ForegroundColor Green
    Write-Host "Idempotent replays: $replayCount" -ForegroundColor Yellow
    Write-Host ""
    
    if ($uniqueOrderIds.Count -eq 1) {
        Write-Host "✅ PASS: Only 1 order created (idempotency working correctly)" -ForegroundColor Green
    } else {
        Write-Host "❌ FAIL: Multiple orders created ($($uniqueOrderIds.Count))" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "Response details:" -ForegroundColor Cyan
    $successful | Format-Table OrderId, Status, Total, IdempotentReplay -AutoSize
}

if ($failed) {
    Write-Host "Failed requests: $($failed.Count)" -ForegroundColor Red
    $failed | Format-Table Error, StatusCode -AutoSize
}

Write-Host ""
Write-Host "=== Test Complete ===" -ForegroundColor Cyan
