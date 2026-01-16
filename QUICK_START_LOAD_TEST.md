# Quick Load Testing Guide (Solo Dev Edition)

**Time to complete**: 30 minutes
**Cost**: $0 (uses mock AWS services)

---

## What This Tests

✅ **Authentication** - Login, registration, JWT tokens
✅ **Database performance** - Connection pooling, credit deductions, queries under load
✅ **Rate limiting** - Your 500/hour and 30/min limits
✅ **API response times** - All endpoints
✅ **Credit system** - Deductions, balance tracking
✅ **Billing** - Stripe webhook handling (without actual charges)

❌ **Not tested** (to avoid AWS charges):
- Actual AWS Polly TTS synthesis
- S3 file uploads
- Textract content extraction

**Mock mode returns fake data for AWS services while testing everything else.**

---

## Step-by-Step Instructions

### 1. Create Test Users (One-time setup)

```bash
# Create a persistent test user for load tests
python setup_test_users.py --persistent

# Output:
# ✓ Created user: loadtest_user@example.com
# Password: TestPassword123!
# Tier: PRO
# Credits: 1,000,000
```

### 2. Start Your Backend in Test Mode

```bash
# Activate virtual environment
source tts_reader_env/bin/activate

# Enable mock mode (important!)
export LOAD_TEST_MODE=true

# Start backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

You should see:
```
🧪 LOAD TEST MODE ENABLED
   AWS Polly and S3 will be mocked (no charges)
```

### 3. Run Load Tests

Open a **new terminal** (keep backend running):

```bash
cd /path/to/tts-reader-aws-backend

# Option A: Interactive script (easiest)
./quick_load_test.sh

# Option B: Manual commands
./run_load_tests.sh smoke --local     # 2 min, 5 users
./run_load_tests.sh load --local      # 5 min, 50 users
./run_load_tests.sh stress --local    # 5 min, 200 users
```

### 4. View Results

Reports are saved to `load_test_reports/`:

```bash
# Open latest HTML report
open load_test_reports/smoke_test_*.html
```

---

## Interpreting Results

### Good Indicators ✅

- **Success rate**: >99% for all endpoints
- **Response times** (p95):
  - `/api/login`: <300ms
  - `/api/synthesize`: <2s (even though it's mocked)
  - `/api/extract`: <3s
- **Database**: No connection pool exhaustion errors
- **Rate limiting**: 429 errors only appear when limits are hit (expected)

### Red Flags 🚩

- **Failures >1%**: Check logs for errors
- **Slow responses**: >5s for any endpoint (database bottleneck?)
- **Database errors**: Connection timeouts, deadlocks
- **Memory issues**: Backend crashes or becomes unresponsive

---

## What Each Test Does

### Smoke Test (2 min, 5 users)
**Purpose**: Validate everything works
**Use case**: Run this first, every time

```bash
./quick_load_test.sh  # Choose option 1
```

### Realistic Load (5 min, 50 users)
**Purpose**: Simulate expected traffic
**Use case**: Your baseline - if this fails, you have problems

```bash
./quick_load_test.sh  # Choose option 2
```

**Calculates to:**
- ~50 concurrent users
- ~500 requests/min
- ~2,500 total requests

### Stress Test (5 min, 200 users)
**Purpose**: Find your breaking point
**Use case**: See where things fail

```bash
./quick_load_test.sh  # Choose option 3
```

**Calculates to:**
- ~200 concurrent users
- ~2,000 requests/min
- ~10,000 total requests

---

## Common Issues & Fixes

### Issue: "Backend is not running"
**Fix**: Start backend with `LOAD_TEST_MODE=true` first

### Issue: "Test user not found"
**Fix**: Run `python setup_test_users.py --persistent`

### Issue: Database connection errors
**Fix**: Increase pool size in `database.py`:
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=20,  # Increase from 10
    max_overflow=30  # Increase from 20
)
```

### Issue: High failure rate (>5%)
**Causes:**
1. Database pool exhausted (see above)
2. Rate limiting too aggressive (expected if testing limits)
3. Application bugs (check logs)

### Issue: Memory leak during long tests
**Fix**: Check for unclosed connections, monitor with:
```bash
# While test is running
ps aux | grep uvicorn
# Watch memory usage
```

---

## Day 1: Your Testing Checklist

**Morning** (2 hours):
- [ ] Set up test users
- [ ] Run smoke test (should pass 100%)
- [ ] Run realistic load test (50 users)
- [ ] Fix any issues found
- [ ] Re-run tests to validate fixes

**Afternoon** (2 hours):
- [ ] Run stress test (200 users)
- [ ] Document breaking point (how many users before errors?)
- [ ] Test rate limiting behavior
- [ ] Check database performance under load
- [ ] Validate credit deduction logic works correctly

**Evening** (1 hour):
- [ ] Run one more realistic load test
- [ ] Review all reports
- [ ] Document max capacity
- [ ] Make launch decision

---

## What's Good Enough to Launch?

**Minimum requirements for solo dev launch:**

✅ Smoke test: 100% success
✅ Realistic load (50 users): >99% success
✅ Response times: All <5s (p95)
✅ No crashes during 5-minute tests
✅ Database connections stable

**Nice to have (but not blockers):**
- Stress test (200 users) passing
- Response times <2s
- Zero errors

---

## After Launch: Monitoring

1. **Keep test users**: Don't delete them
2. **Run weekly tests**: `./quick_load_test.sh` (smoke test)
3. **Before major updates**: Run realistic load test
4. **Monitor real usage**: CloudWatch, Datadog, or logs

---

## Real World Testing (Optional - Costs Money)

If you want to test actual AWS services:

1. **Disable mock mode**:
   ```bash
   # Don't set LOAD_TEST_MODE
   unset LOAD_TEST_MODE
   uvicorn app.main:app --reload
   ```

2. **Run a tiny test**:
   ```bash
   locust --headless --users 2 --spawn-rate 1 --run-time 1m --host http://localhost:5000
   ```

3. **Check AWS costs**: ~$0.50-2 for small tests

---

## Questions & Troubleshooting

### "Should I test on production?"
**No!** Test locally first. Once comfortable, you can test on production during off-peak hours with VERY low user counts (5-10).

### "How many users should I expect at launch?"
**Realistic expectations:**
- Day 1: 10-50 concurrent users (if you market)
- Week 1: 20-100 concurrent users
- Month 1: 50-500 concurrent users

If your tests pass at 50 users, you're good for initial launch.

### "What if I find a bug during load testing?"
**Fix immediately if it's:**
- Database errors
- Authentication failures
- Credit system bugs (over/under charging)

**Fix later if it's:**
- Slow response times (optimize after launch)
- Edge cases that rarely happen
- UX issues

### "How do I know my database can handle it?"
Watch for these during tests:
```bash
# Check Supabase dashboard for:
- Active connections (should be <10)
- Query duration (should be <100ms)
- Error rate (should be 0%)
```

---

## Summary: What You're Actually Testing

**Without spending a dime, this validates:**

1. ✅ Your FastAPI app can handle 50+ concurrent users
2. ✅ Database queries are fast enough under load
3. ✅ Authentication system works reliably
4. ✅ Rate limiting protects your API
5. ✅ Credit deduction logic is correct
6. ✅ Billing webhooks process correctly
7. ✅ No memory leaks or crashes
8. ✅ Connection pooling is configured correctly

**What you won't know until real AWS load:**
- Polly throttling behavior (but you have rate limiting)
- S3 bandwidth limits (unlikely to hit)
- Textract costs under load (monitor in prod)

**This is totally acceptable for a solo dev launch. Ship it!**

---

## Need Help?

- Review HTML reports for detailed metrics
- Check backend logs: `tail -f tts_api_audit.log`
- Supabase dashboard for database health
- GitHub issues if you find bugs in load test setup

Good luck with your launch! 🚀
