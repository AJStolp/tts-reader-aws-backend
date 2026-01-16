# Load Testing - Start Here! 🚀

## You're 100% Ready to Load Test

Everything is set up. Your test user has **1 million credits** (= 1 billion characters). Mock mode is configured to avoid AWS charges.

---

## Quick Start (2 Commands)

### Terminal 1: Start Backend in Test Mode
```bash
cd /Users/astolp/Desktop/Dev/tts-reader-be/tts-reader-aws-backend
source tts_reader_env/bin/activate

# IMPORTANT: Enable mock mode (no AWS charges!)
export LOAD_TEST_MODE=true

# Start backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

**Look for this in the logs:**
```
🧪 LOAD TEST MODE ENABLED
   AWS Polly and S3 will be mocked (no charges)
```

### Terminal 2: Run Load Tests
```bash
cd /Users/astolp/Desktop/Dev/tts-reader-be/tts-reader-aws-backend

# Interactive menu (easiest)
./quick_load_test.sh
```

Choose option 1 (Smoke Test) first to validate everything works.

---

## What Gets Tested (No AWS Charges)

✅ **Your Application**:
- FastAPI endpoints
- Authentication (login, JWT tokens)
- Database queries & connection pooling
- Credit deductions
- Rate limiting (500/hour, 30/min)
- Response times
- Error handling

❌ **Mocked (No Charges)**:
- AWS Polly TTS synthesis
- S3 file uploads
- Textract content extraction

---

## Test Progression

Run tests in this order:

### 1. Smoke Test (Start here!)
```bash
./quick_load_test.sh  # Choose option 1
```
- **Duration**: 2 minutes
- **Users**: 5 concurrent
- **Purpose**: Validate everything works
- **Expected**: 100% success rate

### 2. Realistic Load
```bash
./quick_load_test.sh  # Choose option 2
```
- **Duration**: 5 minutes
- **Users**: 50 concurrent
- **Purpose**: Simulate real launch day traffic
- **Expected**: >99% success rate

### 3. Stress Test
```bash
./quick_load_test.sh  # Choose option 3
```
- **Duration**: 5 minutes
- **Users**: 200 concurrent
- **Purpose**: Find your breaking point
- **Expected**: Identify limits

---

## Reading Results

After each test, open the HTML report:
```bash
open load_test_reports/smoke_test_*.html
```

### Good Signs ✅
- **Failures**: <1%
- **Response Times (p95)**:
  - /api/login: <300ms
  - /api/synthesize: <2s
  - /api/extract: <3s
- **No database connection errors**
- **Rate limiting working** (429 errors when limits hit)

### Red Flags 🚩
- Failures >5%
- Response times >5s
- Database timeouts
- Backend crashes

---

## Common Issues & Quick Fixes

### Backend won't start?
**Check**: Did you set `LOAD_TEST_MODE=true`?

### Test users not working?
**Fix**: Already created! Use these credentials:
- Email: `loadtest_user@example.com`
- Password: `TestPassword123!`

### Database connection errors?
**Fix**: Edit `database.py`, increase `pool_size=20`

### Want to test with real AWS?
**Don't!** Just start without `LOAD_TEST_MODE` set (costs money).
For launch, the mock tests are sufficient.

---

## Your Launch Decision Matrix

### ✅ Safe to Launch If:
- Smoke test: 100% success
- Realistic load (50 users): >99% success
- No crashes during 5-minute tests
- Response times <5s (p95)

### ⚠️ Fix Before Launch:
- Database connection errors
- Authentication failures
- Credit system bugs
- Crashes or memory leaks

### 💡 Optimize Later (Not Blockers):
- Response times 2-5s (annoying but functional)
- Stress test failures (you won't have 200 users day 1)
- Edge case errors

---

## After Testing: Pre-Launch Checklist

- [ ] Smoke test passed (100% success)
- [ ] Realistic load test passed (>99%)
- [ ] Reviewed HTML reports
- [ ] No database issues
- [ ] Backend stable for 5+ minutes under load
- [ ] AWS Polly quota increase requested (if doing high volume)
- [ ] Monitoring/alerting configured (CloudWatch, Sentry, etc.)

---

## Day 1-2 Testing Schedule

**Hour 1**: Setup & smoke test
- ✅ Test user created (done!)
- ✅ Mock mode working (ready!)
- Run smoke test
- Fix any issues

**Hour 2**: Realistic load
- Run 50-user test
- Review results
- Fix critical issues

**Hour 3**: Stress test
- Run 200-user test
- Document breaking point
- Identify bottlenecks

**Hour 4**: Validation
- Re-run realistic load test
- Confirm fixes work
- Generate final reports

**Decision**: Launch or iterate?

---

## Files You'll Use

### Run Tests
- `quick_load_test.sh` - Interactive test runner (use this!)
- `run_load_tests.sh` - Advanced scenarios
- `locustfile.py` - Test definitions (no need to edit)

### Documentation
- `QUICK_START_LOAD_TEST.md` - Detailed guide
- `LOAD_TESTING.md` - Full documentation

### Setup
- `setup_test_users.py` - Create more test users if needed
- `locust.conf` - Configuration (already set up)

### Results
- `load_test_reports/` - HTML/CSV reports saved here

---

## Pro Tips for Solo Devs

1. **Start small**: Smoke test first, always
2. **Don't over-optimize**: Good enough > perfect
3. **Launch early**: You won't have 200 users day 1
4. **Monitor real traffic**: Adjust based on actual usage
5. **Keep testing**: Run weekly smoke tests

---

## Real-World Expectations

**Day 1 Launch**:
- 10-50 concurrent users (if marketed)
- ~500-1000 requests/hour
- You'll handle it if 50-user test passes

**Week 1**:
- 20-100 concurrent users
- Monitor and optimize

**Month 1**:
- 50-500 concurrent users
- Scale infrastructure as needed

---

## When to Ask for Help

### Critical (Fix NOW):
- Database errors
- Auth failures
- Credit system bugs
- Crashes

### Important (Fix Soon):
- Slow responses (>5s)
- High error rates (>5%)
- Memory issues

### Nice to Have (Optimize Later):
- Response times 2-5s
- Edge cases
- Performance tweaks

---

## Quick Reference Commands

```bash
# Terminal 1: Start backend
source tts_reader_env/bin/activate
export LOAD_TEST_MODE=true
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000

# Terminal 2: Run tests
./quick_load_test.sh                    # Interactive menu
./run_load_tests.sh smoke --local       # Direct smoke test
./run_load_tests.sh load --local        # Direct load test
./run_load_tests.sh stress --local      # Direct stress test

# View latest report
open load_test_reports/*.html | tail -1

# Check backend logs
tail -f tts_api_audit.log

# Create more test users (if needed)
python setup_test_users.py --count 20 --tier PRO --credits 100000
```

---

## Summary

You have:
- ✅ Complete load testing infrastructure
- ✅ Mock AWS services (zero cost)
- ✅ Test user with 1M credits
- ✅ Easy-to-run test scripts
- ✅ Comprehensive documentation

**You're ready! Just run the two commands above and start testing.**

Time to completion: ~30 minutes for all tests
Cost: $0 (mocked AWS)
Confidence before launch: HIGH

---

## Need Help?

1. Check the HTML reports first
2. Review backend logs: `tail -f tts_api_audit.log`
3. Read `QUICK_START_LOAD_TEST.md` for details
4. Check Supabase dashboard for database health

**Good luck with your launch! 🚀**

You've got this. The infrastructure is solid. Launch when you're ready!
