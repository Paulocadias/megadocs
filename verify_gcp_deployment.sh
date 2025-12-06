#!/bin/bash
# GCP Deployment Verification Script
# Usage: ./verify_gcp_deployment.sh YOUR_DOMAIN

set -e

DOMAIN="${1:-http://localhost:5000}"

echo "========================================"
echo "   MegaDoc GCP Deployment Verification"
echo "========================================"
echo "Testing: $DOMAIN"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0

test_endpoint() {
    local name=$1
    local url=$2
    local expected_status=${3:-200}
    
    echo -n "Testing $name... "
    
    response=$(curl -s -o /dev/null -w "%{http_code}" "$url" || echo "000")
    
    if [ "$response" = "$expected_status" ]; then
        echo -e "${GREEN}✓ PASS${NC} ($response)"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (Expected $expected_status, got $response)"
        ((FAILED++))
        return 1
    fi
}

test_json_response() {
    local name=$1
    local url=$2
    
    echo -n "Testing $name JSON response... "
    
    response=$(curl -s "$url")
    
    if echo "$response" | grep -q '"success":true\|"status":"healthy"\|"status":"operational"'; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        echo "Response: $response"
        ((FAILED++))
        return 1
    fi
}

test_security_header() {
    local name=$1
    local header=$2
    local url=$3
    
    echo -n "Testing $name header... "
    
    header_value=$(curl -s -I "$url" | grep -i "$header" || echo "")
    
    if [ -n "$header_value" ]; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (Header not found)"
        ((FAILED++))
        return 1
    fi
}

# 1. Health Check
test_endpoint "Health Check" "$DOMAIN/health" 200
test_json_response "Health Check" "$DOMAIN/health"

# 2. API Stats
test_endpoint "API Stats" "$DOMAIN/api/stats" 200
test_json_response "API Stats" "$DOMAIN/api/stats"

# 3. API Formats
test_endpoint "API Formats" "$DOMAIN/api/formats" 200
test_json_response "API Formats" "$DOMAIN/api/formats"

# 4. Security Headers
test_security_header "X-Content-Type-Options" "X-Content-Type-Options" "$DOMAIN/"
test_security_header "X-Frame-Options" "X-Frame-Options" "$DOMAIN/"
test_security_header "Strict-Transport-Security" "Strict-Transport-Security" "$DOMAIN/"

# 5. Web Pages
test_endpoint "Landing Page" "$DOMAIN/" 200
test_endpoint "Convert Page" "$DOMAIN/convert" 200
test_endpoint "Stats Page" "$DOMAIN/stats" 200
test_endpoint "RAG Page" "$DOMAIN/rag" 200
test_endpoint "API Docs" "$DOMAIN/api/docs" 200

# 6. Metrics Endpoint
test_endpoint "Metrics" "$DOMAIN/metrics" 200

# Summary
echo ""
echo "========================================"
echo "   Verification Summary"
echo "========================================"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Deployment is successful.${NC}"
    exit 0
else
    echo -e "${RED}✗ Some checks failed. Please review the errors above.${NC}"
    exit 1
fi

