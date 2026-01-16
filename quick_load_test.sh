#!/bin/bash

# Quick Load Test Script - Solo Dev Edition
# Tests your app without hitting AWS (no charges!)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════╗"
echo "║   TTS Reader Quick Load Test              ║"
echo "║   Solo Dev Edition - No AWS Charges!      ║"
echo "╚════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if backend is running
echo -e "${YELLOW}Checking if backend is running...${NC}"
if curl -s http://localhost:5000/api/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend is running on localhost:5000${NC}"
else
    echo -e "${RED}✗ Backend is not running!${NC}"
    echo ""
    echo "Please start your backend first:"
    echo "  1. source tts_reader_env/bin/activate"
    echo "  2. export LOAD_TEST_MODE=true"
    echo "  3. uvicorn app.main:app --reload --host 0.0.0.0 --port 5000"
    echo ""
    exit 1
fi

# Check if test users exist
echo ""
echo -e "${YELLOW}Checking test users...${NC}"
if python -c "
import os
import sys
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv('DATABASE_CONNECTION_STRING')
if not DATABASE_URL:
    print('❌ DATABASE_CONNECTION_STRING not found')
    sys.exit(1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

result = session.execute(text(\"SELECT COUNT(*) FROM users WHERE email = 'loadtest_user@example.com'\"))
count = result.scalar()
session.close()

if count == 0:
    print('❌ Test user not found')
    sys.exit(1)
else:
    print('✓ Test user exists')
" 2>/dev/null; then
    echo -e "${GREEN}✓ Test user ready${NC}"
else
    echo -e "${YELLOW}⚠ Test user not found. Creating now...${NC}"
    python setup_test_users.py --persistent
fi

# Ask which test to run
echo ""
echo -e "${GREEN}Which load test do you want to run?${NC}"
echo ""
echo "  1) Quick Smoke Test (5 users, 2 min) - Validate everything works"
echo "  2) Realistic Load (50 users, 5 min) - Simulate real traffic"
echo "  3) Stress Test (200 users, 5 min) - Find your limits"
echo "  4) Web UI (manual) - Interactive testing"
echo ""
read -p "Enter choice (1-4): " choice

case $choice in
    1)
        echo ""
        echo -e "${GREEN}Running Smoke Test...${NC}"
        echo "This validates auth, database, rate limiting without AWS charges"
        echo ""
        mkdir -p load_test_reports
        locust --headless \
            --users 5 \
            --spawn-rate 1 \
            --run-time 2m \
            --host http://localhost:5000 \
            --html load_test_reports/smoke_test_$(date +%Y%m%d_%H%M%S).html \
            --csv load_test_reports/smoke_test_$(date +%Y%m%d_%H%M%S)
        ;;
    2)
        echo ""
        echo -e "${GREEN}Running Realistic Load Test...${NC}"
        echo "50 concurrent users for 5 minutes"
        echo ""
        mkdir -p load_test_reports
        locust --headless \
            --users 50 \
            --spawn-rate 5 \
            --run-time 5m \
            --host http://localhost:5000 \
            --html load_test_reports/load_test_$(date +%Y%m%d_%H%M%S).html \
            --csv load_test_reports/load_test_$(date +%Y%m%d_%H%M%S)
        ;;
    3)
        echo ""
        echo -e "${YELLOW}Running Stress Test...${NC}"
        echo "200 concurrent users - this is aggressive!"
        echo ""
        read -p "Continue? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            mkdir -p load_test_reports
            locust --headless \
                --users 200 \
                --spawn-rate 20 \
                --run-time 5m \
                --host http://localhost:5000 \
                --html load_test_reports/stress_test_$(date +%Y%m%d_%H%M%S).html \
                --csv load_test_reports/stress_test_$(date +%Y%m%d_%H%M%S)
        else
            echo "Cancelled."
            exit 0
        fi
        ;;
    4)
        echo ""
        echo -e "${GREEN}Starting Locust Web UI...${NC}"
        echo "Navigate to: ${BLUE}http://localhost:8089${NC}"
        echo ""
        echo "Recommended settings:"
        echo "  - Users: 20-50"
        echo "  - Spawn rate: 5-10"
        echo "  - Host: http://localhost:5000"
        echo ""
        locust --host http://localhost:5000
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✓ Load test complete!${NC}"
echo ""
echo "Reports saved to: load_test_reports/"
ls -lh load_test_reports/*.html 2>/dev/null | tail -1
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. Open the HTML report in your browser"
echo "  2. Check for errors (should be <1%)"
echo "  3. Review response times"
echo "  4. Check database connection pool didn't max out"
echo ""
