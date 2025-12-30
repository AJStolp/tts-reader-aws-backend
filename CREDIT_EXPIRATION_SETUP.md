# Credit Expiration System

## Overview

This system implements **1-year expiration for all credit purchases** starting from the purchase date. Users can make multiple purchases, each with its own expiration date. Credits are tracked in a transaction ledger system with FIFO (first-in, first-out) deduction.

## Key Features

### 1. Transaction Ledger System
- Each credit purchase creates a separate `CreditTransaction` record
- Each transaction has its own 1-year expiration from purchase date
- Credits are deducted FIFO (oldest expiring first)
- Transactions can be: ACTIVE, EXPIRED, or CONSUMED

### 2. Dynamic Tier System
- User tier is calculated based on **total active credits**
- Tier updates automatically when credits are used or expired
- Tier thresholds:
  - **FREE**: < 2,000 credits
  - **PREMIUM**: 2,000-9,999 credits
  - **PRO**: 10,000+ credits

### 3. Frontend Integration
- API returns `next_expiration` and `days_until_expiration` for countdown display
- Frontend can show countdown timer that updates daily
- Progress bar shows total remaining credits across all transactions

### 4. Email Notifications (Ready for Resend)
- **30-day warning**: "Your credits expire in 30 days"
- **7-day warning**: "Your credits expire in 7 days"
- **Expiration notice**: "Your credits have expired"
- Email code is in `app/background_jobs.py` (currently commented out)

## Database Schema

### New Table: `credit_transactions`

```sql
CREATE TABLE credit_transactions (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,

    -- Credits
    credits_purchased INTEGER NOT NULL,
    credits_remaining INTEGER NOT NULL,

    -- Pricing
    purchase_price INTEGER,  -- in cents (e.g., 500 = $5.00)
    tier_at_purchase VARCHAR(20),

    -- Expiration
    purchased_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,  -- purchased_at + 1 year

    -- Status
    status VARCHAR(20) NOT NULL,  -- ACTIVE, EXPIRED, CONSUMED

    -- Stripe metadata
    stripe_payment_id VARCHAR(128),
    stripe_session_id VARCHAR(128),

    -- Timestamps
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP
);
```

### Updated: `users` table
- `credit_balance`: Now a **cached field** (computed from active transactions)
- `tier`: Now **dynamic** (recalculated when credits change)

## Setup Instructions

### 1. Run Database Migration

```bash
# Navigate to project directory
cd /path/to/tts-reader-aws-backend

# Run migration
alembic upgrade head
```

This creates the `credit_transactions` table and necessary indexes.

### 2. Update Existing Credits (If Any)

If you have existing users with credits in the old `credit_balance` field, you can create transactions for them:

```python
from datetime import datetime
from models import User, CreditTransaction, TransactionStatus
from database import SessionLocal

db = SessionLocal()

# Find users with existing credit balance
users_with_credits = db.query(User).filter(User.credit_balance > 0).all()

for user in users_with_credits:
    # Create a transaction for existing credits
    # Set expiration to 1 year from now
    purchased_at = datetime.utcnow()
    expires_at = purchased_at.replace(year=purchased_at.year + 1)

    transaction = CreditTransaction(
        user_id=user.user_id,
        credits_purchased=user.credit_balance,
        credits_remaining=user.credit_balance,
        purchased_at=purchased_at,
        expires_at=expires_at,
        status=TransactionStatus.ACTIVE
    )

    db.add(transaction)

db.commit()
```

### 3. Set Up Background Job (Cron)

The background job expires old credits and sends warning emails. Run it **once per day**.

#### Option A: Crontab

```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 2 AM)
0 2 * * * cd /path/to/tts-reader-aws-backend && /path/to/python -m app.background_jobs >> /var/log/credit-expiration.log 2>&1
```

#### Option B: Python Scheduler (APScheduler)

Create a separate scheduler service:

```python
# scheduler.py
from apscheduler.schedulers.blocking import BlockingScheduler
from app.background_jobs import run_daily_jobs

scheduler = BlockingScheduler()
scheduler.add_job(run_daily_jobs, 'cron', hour=2)  # Run at 2 AM daily
scheduler.start()
```

Run it as a service:
```bash
python scheduler.py
```

#### Option C: AWS Lambda (for production)

Deploy `app/background_jobs.py` as a Lambda function and trigger it with EventBridge (CloudWatch Events) on a daily schedule.

### 4. Enable Email Notifications (Resend)

Once Resend is configured:

1. Add Resend API key to your environment:
   ```bash
   export RESEND_API_KEY="re_xxxxxxxxxxxxx"
   ```

2. Update `app/config.py`:
   ```python
   RESEND_API_KEY = os.getenv("RESEND_API_KEY")
   ```

3. Uncomment the email code in `app/background_jobs.py`:
   - Search for `# Uncomment when Resend is configured:`
   - Uncomment the `resend.emails.send()` blocks in:
     - `send_expiration_warning_email()`
     - `send_expiration_notification_email()`

4. Install Resend SDK:
   ```bash
   pip install resend
   ```

5. Test the emails:
   ```bash
   python -m app.background_jobs
   ```

## API Changes

### GET `/api/payment/credit-balance`

**Before:**
```json
{
  "credit_balance": 5000,
  "tier": "premium",
  "can_use_polly": true
}
```

**After:**
```json
{
  "user_id": "uuid",
  "username": "john",
  "credit_balance": 5000,
  "tier": "PREMIUM",
  "can_use_polly": true,
  "is_active": true,
  "email_verified": true,
  "next_expiration": "2026-12-29T12:00:00Z",
  "days_until_expiration": 365,
  "active_transactions": [
    {
      "id": 1,
      "credits_purchased": 3000,
      "credits_remaining": 2500,
      "purchase_price": 3000,
      "tier_at_purchase": "PREMIUM",
      "purchased_at": "2025-12-29T12:00:00Z",
      "expires_at": "2026-12-29T12:00:00Z",
      "days_until_expiration": 365,
      "status": "ACTIVE",
      "stripe_payment_id": "pi_xxx",
      "created_at": "2025-12-29T12:00:00Z"
    },
    {
      "id": 2,
      "credits_purchased": 2500,
      "credits_remaining": 2500,
      "purchase_price": 2500,
      "tier_at_purchase": "PREMIUM",
      "purchased_at": "2025-12-30T12:00:00Z",
      "expires_at": "2026-12-30T12:00:00Z",
      "days_until_expiration": 366,
      "status": "ACTIVE",
      "stripe_payment_id": "pi_yyy",
      "created_at": "2025-12-30T12:00:00Z"
    }
  ],
  "total_transactions": 2
}
```

## Frontend Implementation

### Display Countdown Timer

```javascript
// Fetch credit balance
const response = await fetch('/api/payment/credit-balance');
const data = await response.json();

// Calculate days remaining
const daysRemaining = data.days_until_expiration;
const expirationDate = new Date(data.next_expiration);

// Display countdown
if (daysRemaining > 0) {
  console.log(`Your credits expire in ${daysRemaining} days`);

  // Show warning if < 30 days
  if (daysRemaining <= 30) {
    showWarningBanner(`⚠️ Your credits expire in ${daysRemaining} days!`);
  }
} else if (daysRemaining === 0) {
  showWarningBanner('⚠️ Your credits expire today!');
}
```

### Display Progress Bar

```javascript
// Show total remaining credits
const totalCredits = data.credit_balance;
const totalCharacters = totalCredits * 1000;

// Progress bar (if you track original purchase total)
// Or just show absolute number:
<div>
  <p>{totalCredits.toLocaleString()} credits remaining</p>
  <p>{totalCharacters.toLocaleString()} characters</p>
</div>
```

## How It Works

### Example: Multiple Purchases

**User Journey:**
1. **Jan 1, 2025**: User buys 2,000 credits → Expires Jan 1, 2026
2. **Jun 1, 2025**: User buys 10,000 credits → Expires Jun 1, 2026
3. **Total active credits**: 12,000 (PRO tier)

**Credit Usage (FIFO):**
- User uses 3,000 credits on Jul 1, 2025
- System deducts:
  - 2,000 from Jan purchase (depleted → CONSUMED)
  - 1,000 from Jun purchase (9,000 remaining)
- **New total**: 9,000 credits (tier stays PRO)

**Expiration:**
- Jun 1, 2026: Jun purchase expires
- Remaining 9,000 credits set to 0
- User downgraded to FREE tier
- Email sent: "Your credits have expired"

## Testing

### Manual Test: Create Test Transaction

```python
from datetime import datetime, timedelta
from models import User, CreditTransaction, TransactionStatus
from database import SessionLocal

db = SessionLocal()
user = db.query(User).filter(User.username == "testuser").first()

# Create transaction expiring in 7 days (for testing warning emails)
purchased_at = datetime.utcnow()
expires_at = purchased_at + timedelta(days=7)

transaction = CreditTransaction(
    user_id=user.user_id,
    credits_purchased=1000,
    credits_remaining=1000,
    purchased_at=purchased_at,
    expires_at=expires_at,
    status=TransactionStatus.ACTIVE
)

db.add(transaction)
db.commit()

# Run background job to test
from app.background_jobs import run_daily_jobs
run_daily_jobs()
```

### Test Stripe Webhook

```bash
# Use Stripe CLI to forward webhooks
stripe listen --forward-to localhost:8000/api/payment/stripe_webhook

# Trigger test checkout
stripe trigger checkout.session.completed
```

## Monitoring

### Check Expiring Credits

```sql
-- Credits expiring in next 30 days
SELECT
    u.username,
    ct.credits_remaining,
    ct.expires_at,
    EXTRACT(DAY FROM (ct.expires_at - NOW())) as days_remaining
FROM credit_transactions ct
JOIN users u ON ct.user_id = u.user_id
WHERE ct.status = 'ACTIVE'
  AND ct.expires_at <= NOW() + INTERVAL '30 days'
ORDER BY ct.expires_at ASC;
```

### Check Expired Transactions

```sql
-- Recently expired
SELECT
    u.username,
    ct.credits_purchased,
    ct.expires_at
FROM credit_transactions ct
JOIN users u ON ct.user_id = u.user_id
WHERE ct.status = 'EXPIRED'
  AND ct.expires_at >= NOW() - INTERVAL '7 days'
ORDER BY ct.expires_at DESC;
```

## Rollback Plan

If you need to rollback:

```bash
# Revert migration
alembic downgrade -1

# This will:
# - Drop credit_transactions table
# - Keep users.credit_balance intact (no data loss)
```

## Support

For issues or questions:
1. Check logs: `/var/log/credit-expiration.log`
2. Review transaction status in database
3. Test background job manually: `python -m app.background_jobs`
