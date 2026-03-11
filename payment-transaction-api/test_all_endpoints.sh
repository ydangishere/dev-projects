#!/bin/bash
# Comprehensive test script for all API endpoints

BASE_URL=${1:-"http://localhost:8000"}

echo "=========================================="
echo "Testing Order/Payment API"
echo "Base URL: $BASE_URL"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

test_endpoint() {
    local name=$1
    local method=$2
    local url=$3
    local headers=$4
    local body=$5
    local expected_status=$6
    
    echo -n "Testing $name... "
    
    if [ -n "$body" ]; then
        if [ -n "$headers" ]; then
            response=$(curl -s -w "\n%{http_code}" -X $method "$url" -H "$headers" -d "$body")
        else
            response=$(curl -s -w "\n%{http_code}" -X $method "$url" -d "$body")
        fi
    else
        if [ -n "$headers" ]; then
            response=$(curl -s -w "\n%{http_code}" -X $method "$url" -H "$headers")
        else
            response=$(curl -s -w "\n%{http_code}" -X $method "$url")
        fi
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body_response=$(echo "$response" | sed '$d')
    
    if [ "$http_code" == "$expected_status" ]; then
        echo -e "${GREEN}✓ PASS${NC} (Status: $http_code)"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (Expected: $expected_status, Got: $http_code)"
        echo "  Response: $body_response"
        ((FAILED++))
        return 1
    fi
}

# Test 1: Root endpoint
echo "1. Root endpoint"
test_endpoint "GET /" "GET" "$BASE_URL/" "" "" "200"
echo ""

# Test 2: Get products (first call - cache miss)
echo "2. GET /products (cache miss)"
test_endpoint "GET /products" "GET" "$BASE_URL/products" "" "" "200"
PRODUCTS_RESPONSE=$(curl -s "$BASE_URL/products")
echo "   Response: $PRODUCTS_RESPONSE"
echo ""

# Test 3: Get products (second call - cache hit)
echo "3. GET /products (cache hit)"
START_TIME=$(date +%s%N)
test_endpoint "GET /products" "GET" "$BASE_URL/products" "" "" "200"
END_TIME=$(date +%s%N)
DURATION=$((($END_TIME - $START_TIME) / 1000000))
echo "   Duration: ${DURATION}ms (should be faster due to cache)"
echo ""

# Test 4: Create order (missing Idempotency-Key) → 422
echo "4. POST /orders (missing Idempotency-Key)"
test_endpoint "POST /orders (no key)" "POST" "$BASE_URL/orders" \
    "Content-Type: application/json" \
    '{"customerId":"c123","items":[{"productId":"p1","qty":1}]}' \
    "422"
echo ""

# Test 5: Create order (first call) → 201
echo "5. POST /orders (first call)"
KEY1="test-key-$(date +%s)"
ORDER_RESPONSE=$(curl -s -X POST "$BASE_URL/orders" \
    -H "Content-Type: application/json" \
    -H "Idempotency-Key: $KEY1" \
    -d '{"customerId":"c123","items":[{"productId":"p1","qty":2},{"productId":"p2","qty":1}]}')
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/orders" \
    -H "Content-Type: application/json" \
    -H "Idempotency-Key: $KEY1" \
    -d '{"customerId":"c123","items":[{"productId":"p1","qty":2},{"productId":"p2","qty":1}]}')

if [ "$HTTP_CODE" == "201" ]; then
    echo -e "${GREEN}✓ PASS${NC} (Status: $HTTP_CODE)"
    ((PASSED++))
    ORDER_ID=$(echo $ORDER_RESPONSE | grep -o '"orderId":"[^"]*"' | cut -d'"' -f4)
    echo "   Order ID: $ORDER_ID"
    echo "   Response: $ORDER_RESPONSE"
else
    echo -e "${RED}✗ FAIL${NC} (Expected: 201, Got: $HTTP_CODE)"
    ((FAILED++))
fi
echo ""

# Test 6: Create order (same key, same body) → 200 with idempotentReplay
echo "6. POST /orders (same key, same body - replay)"
REPLAY_RESPONSE=$(curl -s -X POST "$BASE_URL/orders" \
    -H "Content-Type: application/json" \
    -H "Idempotency-Key: $KEY1" \
    -d '{"customerId":"c123","items":[{"productId":"p1","qty":2},{"productId":"p2","qty":1}]}')
REPLAY_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/orders" \
    -H "Content-Type: application/json" \
    -H "Idempotency-Key: $KEY1" \
    -d '{"customerId":"c123","items":[{"productId":"p1","qty":2},{"productId":"p2","qty":1}]}')

if [ "$REPLAY_CODE" == "200" ] && echo "$REPLAY_RESPONSE" | grep -q "idempotentReplay"; then
    echo -e "${GREEN}✓ PASS${NC} (Status: $REPLAY_CODE, has idempotentReplay)"
    ((PASSED++))
    echo "   Response: $REPLAY_RESPONSE"
else
    echo -e "${RED}✗ FAIL${NC} (Expected: 200 with idempotentReplay, Got: $REPLAY_CODE)"
    ((FAILED++))
fi
echo ""

# Test 7: Create order (same key, different body) → 409
echo "7. POST /orders (same key, different body)"
KEY2="test-key-conflict-$(date +%s)"
curl -s -X POST "$BASE_URL/orders" \
    -H "Content-Type: application/json" \
    -H "Idempotency-Key: $KEY2" \
    -d '{"customerId":"c123","items":[{"productId":"p1","qty":1}]}' > /dev/null

test_endpoint "POST /orders (key reuse)" "POST" "$BASE_URL/orders" \
    "Content-Type: application/json\nIdempotency-Key: $KEY2" \
    '{"customerId":"c999","items":[{"productId":"p2","qty":5}]}' \
    "409"
echo ""

# Test 8: Get order
if [ -n "$ORDER_ID" ]; then
    echo "8. GET /orders/{orderId}"
    test_endpoint "GET /orders/$ORDER_ID" "GET" "$BASE_URL/orders/$ORDER_ID" "" "" "200"
    echo ""
    
    # Test 9: Confirm order
    echo "9. POST /orders/{orderId}/confirm"
    CONFIRM_RESPONSE=$(curl -s -X POST "$BASE_URL/orders/$ORDER_ID/confirm")
    CONFIRM_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/orders/$ORDER_ID/confirm")
    
    if [ "$CONFIRM_CODE" == "200" ]; then
        echo -e "${GREEN}✓ PASS${NC} (Status: $CONFIRM_CODE)"
        ((PASSED++))
        echo "   Response: $CONFIRM_RESPONSE"
    else
        echo -e "${RED}✗ FAIL${NC} (Expected: 200, Got: $CONFIRM_CODE)"
        ((FAILED++))
    fi
    echo ""
    
    # Test 10: Confirm order again (idempotent)
    echo "10. POST /orders/{orderId}/confirm (already confirmed)"
    CONFIRM_REPLAY=$(curl -s -X POST "$BASE_URL/orders/$ORDER_ID/confirm")
    CONFIRM_REPLAY_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/orders/$ORDER_ID/confirm")
    
    if [ "$CONFIRM_REPLAY_CODE" == "200" ] && echo "$CONFIRM_REPLAY" | grep -q "idempotentReplay"; then
        echo -e "${GREEN}✓ PASS${NC} (Status: $CONFIRM_REPLAY_CODE, idempotent)"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC} (Expected: 200 with idempotentReplay)"
        ((FAILED++))
    fi
    echo ""
fi

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo "Total: $((PASSED + FAILED))"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed! ✓${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed ✗${NC}"
    exit 1
fi
