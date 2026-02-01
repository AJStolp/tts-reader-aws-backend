# Session Notes - Jan 28, 2026

## Summary
Debugging registration and payment flow issues for TTS Audify Chrome extension.

---

## Issues Fixed

### 1. Registration 422 Error - FIXED
**Problem:** Registration returning 422 Unprocessable Entity
**Cause:** `first_name` and `last_name` were required fields but the extension form doesn't collect them
**Fix:** Made fields optional in `app/models.py`:
```python
first_name: Optional[str] = Field(default=None, max_length=128)
last_name: Optional[str] = Field(default=None, max_length=128)
```
Also updated `app/auth.py` `create_user_account()` to use `.get()` for these fields.

### 2. Registration 500 Error (bcrypt) - FIXED
**Problem:** `password cannot be longer than 72 bytes` error
**Cause:** bcrypt 5.0.0 incompatible with passlib 1.7.4
**Fix:** Downgraded bcrypt on server:
```bash
pip3 install bcrypt==4.0.1
```
Note: `requirements.txt` already has `bcrypt==4.0.1` pinned - server just had wrong version installed.

### 3. Credit Purchase 403 Error - FIXED
**Problem:** `/api/create-credit-checkout` returning 403
**Cause:** User email not verified
**Fix:** Either verify email via link, or manually set `email_verified = true` in database for testing.

---

## Current Issue - IN PROGRESS

### Stripe Webhook Not Updating Credits
**Problem:** Payment completes successfully in Stripe but credits don't get added to user's account.

**Root Cause Found:** `checkout.session.completed` event is NOT firing - only `payment_intent.*` events are showing.

**Investigation Status:**
- Backend code is CORRECT - uses `stripe.checkout.Session.create()` (see `app/services.py` line 669)
- Webhook endpoint created at: `https://api.unchonk.com/api/stripe_webhook`
- Webhook handler expects `checkout.session.completed` event (see `app/services.py` line 782)

**Next Steps:**
1. Verify webhook is configured to listen for `checkout.session.completed` event type
   - Stripe Dashboard → Developers → Webhooks → click endpoint → check "Events to send"
   - Must include: `checkout.session.completed`

2. Verify webhook signing secret is in server `.env`:
   ```bash
   grep STRIPE_WEBHOOK .env
   # Should show: STRIPE_WEBHOOK_SECRET=whsec_xxxxx
   ```

3. After fixing webhook config, restart server:
   ```bash
   kill -9 $(pgrep -f uvicorn)
   # Server auto-restarts via some process manager
   ```

4. Test payment again and check:
   - Stripe Dashboard → Events → filter `checkout.session.completed`
   - Stripe Dashboard → Webhooks → endpoint → Recent deliveries
   - Server logs: `sudo journalctl --since "5 minutes ago" --no-pager | grep -i "webhook\|stripe\|credit"`

**Note:** Need SEPARATE webhooks for Test mode vs Live mode in Stripe.

---

## Server Management Notes

### EC2 Server Access
- Server has auto-respawning uvicorn process (something keeps restarting it)
- To restart: just kill it and it auto-restarts
```bash
kill -9 $(pgrep -f uvicorn)
# or
sudo fuser -k 5000/tcp
```

### Checking Logs
```bash
# Recent logs
sudo journalctl --since "5 minutes ago" --no-pager

# Filter for specific terms
sudo journalctl --since "5 minutes ago" --no-pager | grep -i "webhook\|stripe\|error"

# Webhook specific
sudo journalctl --since "5 minutes ago" --no-pager | grep -i "checkout.session.completed"
```

### Server File Locations
- App code: `/home/ec2-user/tts-reader-aws-backend/`
- Env file: `/home/ec2-user/tts-reader-aws-backend/.env`
- Python: `python3` (not `python`)

### Deploying Code Changes
```bash
# On server
cd /home/ec2-user/tts-reader-aws-backend
git pull
kill -9 $(pgrep -f uvicorn)
# Server auto-restarts
```

### Clearing Python Cache (if code changes not taking effect)
```bash
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
```

---

## Key Files

| File | Purpose |
|------|---------|
| `app/models.py` | Pydantic models (UserCreate, etc.) |
| `app/auth.py` | Auth logic, `create_user_account()` |
| `app/routes.py` | API endpoints including `/api/stripe_webhook` |
| `app/services.py` | Stripe service, `handle_webhook_event()`, `create_credit_checkout_session()` |
| `models.py` (root) | SQLAlchemy DB models, `User.set_password()` |
| `requirements.txt` | Dependencies (bcrypt==4.0.1 pinned) |

---

## Stripe Webhook Handler Flow
1. `POST /api/stripe_webhook` receives event from Stripe
2. Calls `stripe_service.handle_webhook_event()` in `app/services.py`
3. Verifies signature with `STRIPE_WEBHOOK_SECRET`
4. On `checkout.session.completed`:
   - Extracts `username` from `client_reference_id` or metadata
   - Finds user in DB
   - If `purchase_type == "credits"`: calls `user.purchase_credits()`
   - Commits to DB

---

## Test User
- Username: `stony2`
- Email: `testdeznutz@gmail.com`
- Email verified: `true` (manually set)
- Current credits: `0` (webhook not working yet)
