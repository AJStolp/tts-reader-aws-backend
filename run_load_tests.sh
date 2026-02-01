#!/bin/bash

# TTS Reader Load Testing Runner
# Quick access to common load test scenarios

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
LOCUST_FILE="locustfile.py"
CONFIG_FILE="locust.conf"
REPORT_DIR="load_test_reports"

# Create reports directory
mkdir -p "$REPORT_DIR"

# Print banner
print_banner() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════╗"
    echo "║   TTS Reader Load Testing Suite           ║"
    echo "║   Powered by Locust                       ║"
    echo "╚════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Print usage
print_usage() {
    echo -e "${GREEN}Usage:${NC} ./run_load_tests.sh [scenario] [options]"
    echo ""
    echo -e "${GREEN}Available scenarios:${NC}"
    echo "  smoke       - Quick validation (5 users, 2 min)"
    echo "  load        - Standard production load (100 users, 10 min)"
    echo "  stress      - High load stress test (500 users, 10 min)"
    echo "  spike       - Sudden traffic spike (ramp 10→300 users)"
    echo "  endurance   - Long-running stability (50 users, 2 hours)"
    echo "  critical    - Critical revenue paths only (100 users, 10 min)"
    echo "  burst       - Burst traffic users only (200 users, 5 min)"
    echo "  power       - Power users only (100 users, 10 min)"
    echo "  web         - Launch web UI for manual testing"
    echo ""
    echo -e "${GREEN}Options:${NC}"
    echo "  --host URL  - Override target host (e.g., --host https://api.example.com)"
    echo "  --local     - Use local backend (http://localhost:5000)"
    echo "  --prod      - Use production backend (update in script)"
    echo ""
    echo -e "${GREEN}Examples:${NC}"
    echo "  ./run_load_tests.sh smoke --local"
    echo "  ./run_load_tests.sh load --host https://staging-api.example.com"
    echo "  ./run_load_tests.sh web"
    echo ""
}

# Parse options
HOST=""
for arg in "$@"; do
    case $arg in
        --host=*)
            HOST="${arg#*=}"
            shift
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --local)
            HOST="http://localhost:5000"
            shift
            ;;
        --prod)
            HOST="https://api.unchonk.com"  # UPDATE THIS with your production URL
            shift
            ;;
    esac
done

# Get scenario
SCENARIO="${1:-help}"

# Add host flag if specified
HOST_FLAG=""
if [ -n "$HOST" ]; then
    HOST_FLAG="--host $HOST"
    echo -e "${YELLOW}Target Host:${NC} $HOST"
fi

# Generate timestamp for reports
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

print_banner

case $SCENARIO in
    smoke)
        echo -e "${GREEN}Running Smoke Test...${NC}"
        echo "Purpose: Quick validation that system is working"
        echo "Users: 5, Spawn Rate: 1/sec, Duration: 2 min"
        echo ""
        locust --headless \
            --users 5 \
            --spawn-rate 1 \
            --run-time 2m \
            --config=$CONFIG_FILE \
            $HOST_FLAG \
            --html "$REPORT_DIR/smoke_test_${TIMESTAMP}.html" \
            --csv "$REPORT_DIR/smoke_test_${TIMESTAMP}"
        echo -e "${GREEN}✓ Smoke test complete!${NC}"
        ;;

    load)
        echo -e "${GREEN}Running Load Test...${NC}"
        echo "Purpose: Simulate expected production traffic"
        echo "Users: 100, Spawn Rate: 10/sec, Duration: 10 min"
        echo ""
        locust --headless \
            --users 100 \
            --spawn-rate 10 \
            --run-time 10m \
            --config=$CONFIG_FILE \
            $HOST_FLAG \
            --html "$REPORT_DIR/load_test_${TIMESTAMP}.html" \
            --csv "$REPORT_DIR/load_test_${TIMESTAMP}"
        echo -e "${GREEN}✓ Load test complete!${NC}"
        ;;

    stress)
        echo -e "${YELLOW}Running Stress Test...${NC}"
        echo "Purpose: Find system breaking point"
        echo "Users: 500, Spawn Rate: 50/sec, Duration: 10 min"
        echo -e "${RED}WARNING: This is an aggressive test!${NC}"
        echo ""
        read -p "Continue? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            locust --headless \
                --users 500 \
                --spawn-rate 50 \
                --run-time 10m \
                --config=$CONFIG_FILE \
                $HOST_FLAG \
                --html "$REPORT_DIR/stress_test_${TIMESTAMP}.html" \
                --csv "$REPORT_DIR/stress_test_${TIMESTAMP}"
            echo -e "${GREEN}✓ Stress test complete!${NC}"
        else
            echo "Cancelled."
        fi
        ;;

    spike)
        echo -e "${YELLOW}Running Spike Test...${NC}"
        echo "Purpose: Test sudden traffic surge"
        echo "Starting with 10 users, then spike to 300"
        echo ""
        echo "This test requires manual intervention:"
        echo "1. Starting Locust web UI..."
        echo "2. Navigate to http://localhost:8089"
        echo "3. Start with 10 users at 2 users/sec"
        echo "4. After 2 minutes, increase to 300 users at 100 users/sec"
        echo "5. Monitor for 5 minutes, then stop"
        echo ""
        read -p "Press Enter to launch web UI..."
        locust --config=$CONFIG_FILE $HOST_FLAG
        ;;

    endurance)
        echo -e "${BLUE}Running Endurance Test...${NC}"
        echo "Purpose: Long-running stability test (memory leaks, resource exhaustion)"
        echo "Users: 50, Spawn Rate: 5/sec, Duration: 2 hours"
        echo -e "${YELLOW}This will take 2 hours. Consider running in background.${NC}"
        echo ""
        read -p "Continue? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            locust --headless \
                --users 50 \
                --spawn-rate 5 \
                --run-time 2h \
                --config=$CONFIG_FILE \
                $HOST_FLAG \
                --html "$REPORT_DIR/endurance_test_${TIMESTAMP}.html" \
                --csv "$REPORT_DIR/endurance_test_${TIMESTAMP}" \
                > "$REPORT_DIR/endurance_test_${TIMESTAMP}.log" 2>&1 &

            PID=$!
            echo -e "${GREEN}Endurance test running in background (PID: $PID)${NC}"
            echo "Monitor progress: tail -f $REPORT_DIR/endurance_test_${TIMESTAMP}.log"
            echo "Stop test: kill $PID"
        else
            echo "Cancelled."
        fi
        ;;

    critical)
        echo -e "${GREEN}Running Critical Path Test...${NC}"
        echo "Purpose: Test only critical revenue-generating endpoints"
        echo "Users: 100, Spawn Rate: 10/sec, Duration: 10 min"
        echo "Tags: critical, revenue"
        echo ""
        locust --headless \
            --users 100 \
            --spawn-rate 10 \
            --run-time 10m \
            --tags critical,revenue \
            --config=$CONFIG_FILE \
            $HOST_FLAG \
            --html "$REPORT_DIR/critical_test_${TIMESTAMP}.html" \
            --csv "$REPORT_DIR/critical_test_${TIMESTAMP}"
        echo -e "${GREEN}✓ Critical path test complete!${NC}"
        ;;

    burst)
        echo -e "${YELLOW}Running Burst Traffic Test...${NC}"
        echo "Purpose: Simulate aggressive burst traffic (viral content, campaigns)"
        echo "User Type: BurstTrafficUser (aggressive, short wait times)"
        echo "Users: 200, Spawn Rate: 50/sec, Duration: 5 min"
        echo ""
        locust BurstTrafficUser --headless \
            --users 200 \
            --spawn-rate 50 \
            --run-time 5m \
            --config=$CONFIG_FILE \
            $HOST_FLAG \
            --html "$REPORT_DIR/burst_test_${TIMESTAMP}.html" \
            --csv "$REPORT_DIR/burst_test_${TIMESTAMP}"
        echo -e "${GREEN}✓ Burst traffic test complete!${NC}"
        ;;

    power)
        echo -e "${BLUE}Running Power User Test...${NC}"
        echo "Purpose: Simulate heavy TTS usage (Premium/Pro tier users)"
        echo "User Type: HeavyTTSUser (70% TTS synthesis)"
        echo "Users: 100, Spawn Rate: 10/sec, Duration: 10 min"
        echo ""
        locust HeavyTTSUser --headless \
            --users 100 \
            --spawn-rate 10 \
            --run-time 10m \
            --config=$CONFIG_FILE \
            $HOST_FLAG \
            --html "$REPORT_DIR/power_user_test_${TIMESTAMP}.html" \
            --csv "$REPORT_DIR/power_user_test_${TIMESTAMP}"
        echo -e "${GREEN}✓ Power user test complete!${NC}"
        ;;

    web)
        echo -e "${GREEN}Launching Locust Web UI...${NC}"
        echo "Navigate to: ${BLUE}http://localhost:8089${NC}"
        echo ""
        echo "Configuration options:"
        echo "  - Number of users: Start with 10-50"
        echo "  - Spawn rate: 5-10 users/sec"
        echo "  - Host: $HOST (or enter manually)"
        echo ""
        locust --config=$CONFIG_FILE $HOST_FLAG
        ;;

    all)
        echo -e "${YELLOW}Running Complete Test Suite...${NC}"
        echo "This will run: smoke → load → stress → critical"
        echo ""
        read -p "Continue? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "\n${GREEN}[1/4] Smoke Test${NC}"
            $0 smoke $HOST_FLAG

            echo -e "\n${GREEN}[2/4] Load Test${NC}"
            sleep 30  # Cool-down period
            $0 load $HOST_FLAG

            echo -e "\n${GREEN}[3/4] Stress Test${NC}"
            sleep 30
            $0 stress $HOST_FLAG

            echo -e "\n${GREEN}[4/4] Critical Path Test${NC}"
            sleep 30
            $0 critical $HOST_FLAG

            echo -e "\n${GREEN}✓ Complete test suite finished!${NC}"
            echo "Reports saved in: $REPORT_DIR"
        else
            echo "Cancelled."
        fi
        ;;

    help|--help|-h|"")
        print_usage
        ;;

    *)
        echo -e "${RED}Error: Unknown scenario '$SCENARIO'${NC}"
        echo ""
        print_usage
        exit 1
        ;;
esac

# Print report location if test completed
if [ -d "$REPORT_DIR" ] && [ "$SCENARIO" != "web" ] && [ "$SCENARIO" != "help" ] && [ "$SCENARIO" != "spike" ]; then
    echo ""
    echo -e "${BLUE}Reports saved to:${NC}"
    ls -lh "$REPORT_DIR"/*${TIMESTAMP}* 2>/dev/null || true
fi
