# Load Testing Guide for TTS Reader Backend

This guide covers comprehensive load testing using Locust for the TTS Reader AWS Backend.

## Table of Contents
- [Quick Start](#quick-start)
- [Test Scenarios](#test-scenarios)
- [User Types](#user-types)
- [Running Tests](#running-tests)
- [Interpreting Results](#interpreting-results)
- [Best Practices](#best-practices)

---

## Quick Start

### Prerequisites
```bash
# Ensure Locust is installed
pip install locust

# Ensure your backend is running (local or deployed)
# Update the 'host' in locust.conf to match your target
```

### Basic Test Run

**Option 1: Using Web UI (Recommended for first runs)**
```bash
# Start Locust web interface
locust --config=locust.conf

# Open browser to http://localhost:8089
# Configure: Number of users, Spawn rate, Host (if not in config)
# Click "Start Swarming"
```

**Option 2: Headless Mode (For CI/CD)**
```bash
# Run with 50 users, spawn 5 per second, run for 5 minutes
locust --headless --users 50 --spawn-rate 5 --run-time 5m --config=locust.conf
```

---

## Test Scenarios

### 1. Smoke Test (Verify system works)
```bash
locust --headless --users 5 --spawn-rate 1 --run-time 2m --config=locust.conf
```
**Purpose**: Quick sanity check before larger tests
**Expected**: 100% success rate, <500ms response times

### 2. Load Test (Normal production traffic)
```bash
locust --headless --users 100 --spawn-rate 10 --run-time 10m --config=locust.conf
```
**Purpose**: Simulate expected production load
**Expected**: >99% success rate, <1s response times for most endpoints

### 3. Stress Test (Find breaking point)
```bash
locust --headless --users 500 --spawn-rate 50 --run-time 10m --config=locust.conf
```
**Purpose**: Identify system limits and failure modes
**Expected**: Gradual degradation, identify bottlenecks

### 4. Spike Test (Sudden traffic surge)
```bash
# Start with low users, then manually scale up in UI
locust --users 10 --spawn-rate 2 --config=locust.conf
# Then increase to 300 users at 100/sec spawn rate
```
**Purpose**: Test auto-scaling, cache warming, rate limiting
**Expected**: System recovers after spike, no crashes

### 5. Endurance Test (Memory leaks, resource exhaustion)
```bash
locust --headless --users 50 --spawn-rate 5 --run-time 2h --config=locust.conf
```
**Purpose**: Long-running stability test
**Expected**: Stable performance over time, no memory leaks

### 6. Critical Path Test (Revenue-generating endpoints only)
```bash
locust --headless --users 100 --spawn-rate 10 --run-time 10m \
  --tags critical,revenue --config=locust.conf
```
**Purpose**: Focus on TTS synthesis and billing endpoints
**Expected**: Ultra-low latency, zero errors

---

## User Types

The locustfile defines 4 user personas with different behavior patterns:

### 1. **TTSReaderUser** (Default, Balanced)
- **Weight Distribution**: 40% TTS, 30% Extraction, 20% Preferences/Billing, 10% Auth/Health
- **Wait Time**: 1-5 seconds between requests
- **Simulates**: Typical user mixing content extraction and TTS synthesis

### 2. **BurstTrafficUser** (Aggressive)
- **Weight Distribution**: 50% TTS, 40% Extraction, 10% Health
- **Wait Time**: 0.5-2 seconds (faster)
- **Simulates**: Viral content spike, marketing campaign surge

### 3. **HeavyTTSUser** (Power Users)
- **Weight Distribution**: 70% TTS, 20% Extraction, 10% Billing
- **Wait Time**: 2-4 seconds
- **Simulates**: Premium/Pro tier users with high character usage

### 4. **ReadOnlyUser** (Browsing)
- **Weight Distribution**: 40% Billing, 30% Health, 20% Preferences, 10% Auth
- **Wait Time**: 3-8 seconds
- **Simulates**: Trial users, feature evaluation, window shoppers

### Running Specific User Types
```bash
# Only HeavyTTSUser (power users)
locust HeavyTTSUser --headless --users 50 --spawn-rate 5 --config=locust.conf

# Only BurstTrafficUser (stress test)
locust BurstTrafficUser --headless --users 200 --spawn-rate 50 --config=locust.conf

# Multiple user types with custom ratios
locust TTSReaderUser HeavyTTSUser --headless --users 100 --spawn-rate 10
```

---

## Running Tests

### Local Backend Testing
```bash
# Update locust.conf:
# host = http://localhost:5000

# Start your backend
cd /path/to/tts-reader-aws-backend
source tts_reader_env/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 5000

# In another terminal, run Locust
locust --config=locust.conf
```

### Production Backend Testing
```bash
# Update locust.conf:
# host = https://api.ttsaudify.com  # Your production URL

# Run test (be careful with production!)
locust --headless --users 50 --spawn-rate 5 --run-time 5m --config=locust.conf
```

### Tag-Based Testing

Test only specific features:
```bash
# Only authentication endpoints
locust --tags auth --config=locust.conf

# Only critical revenue-generating endpoints
locust --tags critical,revenue --config=locust.conf

# Exclude slow/expensive tests
locust --exclude-tags enterprise --config=locust.conf
```

Available tags:
- `auth` - Authentication flows
- `critical` - Mission-critical endpoints
- `revenue` - Revenue-generating features (TTS, billing)
- `extraction` - Content extraction endpoints
- `tts` - Text-to-speech synthesis
- `billing` - Payment and credit operations
- `preferences` - User settings
- `health` - Health checks and monitoring
- `enterprise` - Enterprise features

---

## Interpreting Results

### Key Metrics to Monitor

#### 1. **Request Statistics** (in Web UI or CSV)
- **Total Requests**: Volume handled
- **Failures**: Error rate (aim for <1%)
- **RPS** (Requests/sec): Throughput capacity
- **Response Times**: 50th, 95th, 99th percentiles

#### 2. **Response Time Targets**
| Endpoint | Target (p95) | Max Acceptable |
|----------|--------------|----------------|
| `/api/health` | <100ms | 200ms |
| `/api/login` | <300ms | 500ms |
| `/api/synthesize` | <2s | 5s |
| `/api/extract` | <3s | 10s |
| `/api/extract-and-synthesize` | <5s | 15s |

#### 3. **Success Rate Targets**
- **Critical endpoints** (auth, TTS, billing): 100%
- **Standard endpoints**: >99.5%
- **Enhanced features**: >98%

#### 4. **System Health During Test**
Monitor server-side:
```bash
# CPU/Memory usage
top
htop

# Database connections
# Check Supabase dashboard or PostgreSQL logs

# AWS service health
# CloudWatch metrics for Polly, S3, Textract

# Application logs
tail -f tts_api_audit.log
```

### Report Files Generated

After test completion:
- `load_test_report.html` - Visual HTML report with charts
- `load_test_stats.csv` - Raw request statistics
- `load_test_stats_failures.csv` - Failed request details
- `load_test_stats_history.csv` - Time-series data

### Common Issues and Solutions

| Issue | Possible Cause | Solution |
|-------|---------------|----------|
| High failure rate on `/api/synthesize` | AWS Polly rate limits | Reduce concurrent users or implement request queuing |
| 402 Payment Required errors | Test users out of credits | Create test users with sufficient credits or use mock billing |
| 429 Rate Limit errors | Rate limiting triggered | Adjust `RATE_LIMIT_REQUESTS_PER_HOUR` in config |
| Slow `/api/extract` | Textract delays or complex pages | Test with simpler URLs, monitor Textract quotas |
| Database connection errors | Connection pool exhausted | Increase pool size in `database.py` |
| 401 Unauthorized | JWT token expiration | Tokens expire after 60 min, re-login or extend `ACCESS_TOKEN_EXPIRE_MINUTES` |

---

## Best Practices

### Before Testing

1. **Create dedicated test accounts**
   ```sql
   -- Add test users with sufficient credits
   INSERT INTO users (email, password_hash, tier, is_verified)
   VALUES ('loadtest_user@example.com', '<hash>', 'PRO', true);
   ```

2. **Configure test environment**
   - Use separate database/S3 bucket for load testing
   - Disable email sending (or use test email service)
   - Increase AWS service quotas if needed

3. **Backup production data**
   - Never run aggressive tests on production without backup
   - Consider using a staging environment

### During Testing

1. **Start small, scale up**
   - Begin with 10 users, gradually increase
   - Monitor system health continuously

2. **Watch for cascading failures**
   - AWS service throttling → retry storms → database overload
   - Implement circuit breakers if needed

3. **Monitor external dependencies**
   - Stripe API limits
   - AWS Polly quotas (100 req/sec default)
   - Supabase connection limits

### After Testing

1. **Clean up test data**
   ```bash
   # Remove test users and their data
   # Delete S3 test audio files
   # Reset test account credits
   ```

2. **Analyze bottlenecks**
   - Identify slowest endpoints
   - Review database query performance
   - Check AWS CloudWatch for service throttling

3. **Optimize and re-test**
   - Implement caching for frequently accessed data
   - Optimize database queries (add indexes)
   - Consider async processing for heavy operations

---

## Advanced Scenarios

### Testing WebSocket Progress Updates
```python
# Add to locustfile.py for WebSocket testing
from locust import events
import websocket

# WebSocket connection test (requires additional setup)
# See Locust docs for WebSocket support
```

### Distributed Load Testing (Multiple Machines)

**Master node:**
```bash
locust --master --config=locust.conf
```

**Worker nodes:**
```bash
locust --worker --master-host=<master-ip> --config=locust.conf
```

### Continuous Load Testing (CI/CD Integration)

```yaml
# .github/workflows/load-test.yml
name: Load Test
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install Locust
        run: pip install locust
      - name: Run Load Test
        run: |
          locust --headless --users 50 --spawn-rate 5 --run-time 5m \
            --host ${{ secrets.API_HOST }} \
            --csv load_test_results
      - name: Upload Results
        uses: actions/upload-artifact@v2
        with:
          name: load-test-results
          path: load_test_results*
```

---

## Support and Troubleshooting

### Locust Documentation
- Official Docs: https://docs.locust.io/
- GitHub: https://github.com/locustio/locust

### TTS Reader Specific Issues
- Check application logs: `tts_api_audit.log`
- Review AWS CloudWatch logs
- Monitor Supabase dashboard for DB performance
- Check Stripe dashboard for payment webhook delivery

### Getting Help
```bash
# Locust help
locust --help

# Verbose logging for debugging
locust --loglevel DEBUG --config=locust.conf
```

---

## Quick Reference Commands

```bash
# Smoke test (quick validation)
locust --headless -u 5 -r 1 -t 2m

# Standard load test
locust --headless -u 100 -r 10 -t 10m

# Stress test (find limits)
locust --headless -u 500 -r 50 -t 10m

# Critical paths only
locust --headless -u 100 -r 10 -t 10m --tags critical

# Web UI (interactive)
locust

# Specific user type
locust HeavyTTSUser --headless -u 50 -r 5 -t 5m

# Generate report
locust --headless -u 100 -r 10 -t 5m --html report.html --csv stats
```

**Legend:**
- `-u`: Number of users
- `-r`: Spawn rate (users/second)
- `-t`: Run time (e.g., 5m, 1h)
- `--headless`: No web UI
- `--tags`: Filter by tags
- `--html`: HTML report output
- `--csv`: CSV stats output

---

## Next Steps

1. **Start with smoke test** to verify everything works
2. **Run load test** with expected production traffic
3. **Analyze results** and identify bottlenecks
4. **Optimize** based on findings
5. **Re-test** to validate improvements
6. **Gradually increase** load until you find system limits
7. **Document** acceptable thresholds and capacity planning

Good luck with your load testing!
