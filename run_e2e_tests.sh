#!/bin/bash

# TTS Reader E2E Test Runner
# Tests real user flows against the backend

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
AWS_URL="${1:-http://3.92.11.167:5000}"
LOCAL_URL="http://localhost:5000"
TEST_EMAIL="loadtest_user@example.com"
TEST_PASSWORD="TestPassword123!"

print_banner() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════╗"
    echo "║   TTS Reader E2E Test Suite               ║"
    echo "║   Real User Flow Testing                  ║"
    echo "╚════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_usage() {
    echo -e "${GREEN}Usage:${NC} ./run_e2e_tests.sh [target]"
    echo ""
    echo -e "${GREEN}Targets:${NC}"
    echo "  --local     Test against local backend (http://localhost:5000)"
    echo "  --aws       Test against AWS backend (http://3.92.11.167:5000)"
    echo "  --url URL   Test against custom URL"
    echo ""
    echo -e "${GREEN}Examples:${NC}"
    echo "  ./run_e2e_tests.sh --local"
    echo "  ./run_e2e_tests.sh --aws"
    echo "  ./run_e2e_tests.sh --url https://api.unchonk.com"
    echo ""
}

# Parse arguments
TARGET_URL=""
case "${1}" in
    --local)
        TARGET_URL="$LOCAL_URL"
        echo -e "${YELLOW}Testing against LOCAL backend${NC}"
        ;;
    --aws)
        TARGET_URL="$AWS_URL"
        echo -e "${YELLOW}Testing against AWS backend${NC}"
        ;;
    --url)
        TARGET_URL="${2}"
        echo -e "${YELLOW}Testing against custom URL: $TARGET_URL${NC}"
        ;;
    --help|-h|help|"")
        print_banner
        print_usage
        exit 0
        ;;
    *)
        TARGET_URL="${1}"
        echo -e "${YELLOW}Testing against: $TARGET_URL${NC}"
        ;;
esac

if [ -z "$TARGET_URL" ]; then
    echo -e "${RED}Error: No target URL specified${NC}"
    print_usage
    exit 1
fi

print_banner

# Check if backend is reachable
echo -e "${BLUE}Checking if backend is reachable...${NC}"
if curl -s --connect-timeout 5 "$TARGET_URL/api/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend is reachable${NC}"
else
    echo -e "${RED}✗ Cannot reach backend at $TARGET_URL${NC}"
    echo -e "${YELLOW}Make sure the backend is running and the URL is correct${NC}"
    exit 1
fi

echo ""

# Activate virtual environment if exists
if [ -d "tts_reader_env" ]; then
    echo -e "${BLUE}Activating virtual environment...${NC}"
    source tts_reader_env/bin/activate
fi

# Check if requests library is installed
if ! python3 -c "import requests" 2>/dev/null; then
    echo -e "${YELLOW}Installing requests library...${NC}"
    pip install requests
fi

echo ""

# Run E2E tests
echo -e "${GREEN}Running E2E tests...${NC}"
echo ""

python3 e2e_tests.py "$TARGET_URL" "$TEST_EMAIL" "$TEST_PASSWORD"

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   ✅ E2E Tests PASSED!                     ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
else
    echo -e "${RED}╔════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║   ❌ E2E Tests FAILED                      ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════╝${NC}"
fi

exit $EXIT_CODE
