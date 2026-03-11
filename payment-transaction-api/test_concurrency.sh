#!/bin/bash
# Test Concurrency Script for Order API
# Usage: ./test_concurrency.sh [base_url]

BASE_URL=${1:-"http://localhost:8000"}

echo "=== Order API Concurrency Test ==="
echo "Base URL: $BASE_URL"
echo ""

# Generate unique key
KEY="concurrent-test-$(date +%s)"
echo "Using Idempotency-Key: $KEY"
echo ""

# Prepare request
URL="$BASE_URL/orders"
BODY='{"customerId":"c123","items":[{"productId":"p1","qty":2},{"productId":"p2","qty":1}]}'

echo "Sending 10 concurrent requests..."

# Measure time
START_TIME=$(date +%s.%N)

# Send 10 concurrent requests and save responses
for i in {1..10}; do
  curl -s -X POST "$URL" \
    -H "Content-Type: application/json" \
    -H "Idempotency-Key: $KEY" \
    -d "$BODY" \
    -w "\n" > "/tmp/response_$i.json" &
done

# Wait for all requests to complete
wait

END_TIME=$(date +%s.%N)
DURATION=$(echo "$END_TIME - $START_TIME" | bc)

# Analyze results
echo ""
echo "=== Results ==="
echo "Total requests: 10"
echo "Duration: $(printf "%.2f" $DURATION) seconds"
echo ""

# Count unique orderIds
UNIQUE_ORDER_IDS=$(cat /tmp/response_*.json | jq -r '.orderId' | sort -u | wc -l)
REPLAY_COUNT=$(cat /tmp/response_*.json | jq -r 'select(.idempotentReplay == true)' | wc -l)

echo "Unique orderIds created: $UNIQUE_ORDER_IDS"
echo "Idempotent replays: $REPLAY_COUNT"
echo ""

if [ "$UNIQUE_ORDER_IDS" -eq 1 ]; then
  echo "✅ PASS: Only 1 order created (idempotency working correctly)"
else
  echo "❌ FAIL: Multiple orders created ($UNIQUE_ORDER_IDS)"
fi

echo ""
echo "Response details:"
cat /tmp/response_*.json | jq -r '[.orderId, .status, .total, .idempotentReplay] | @tsv' | column -t

# Cleanup
rm -f /tmp/response_*.json

echo ""
echo "=== Test Complete ==="
