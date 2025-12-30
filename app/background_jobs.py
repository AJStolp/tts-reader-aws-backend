"""
Background jobs for credit expiration and email notifications.

Run this file daily via cron or scheduler to:
1. Expire old credit transactions (1 year from purchase)
2. Send warning emails (30 days, 7 days before expiration)
3. Send expiration notification emails
"""

import sys
import os
from datetime import datetime, timedelta
from typing import List, Tuple

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker, Session
from models import User, CreditTransaction, TransactionStatus, UserTier
from app.config import config
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============ DATABASE SETUP ============

def get_db_session() -> Session:
    """Create database session for background jobs"""
    engine = create_engine(config.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


# ============ EMAIL NOTIFICATIONS ============
# TODO: Uncomment and configure when Resend is implemented

def send_expiration_warning_email(user: User, days_remaining: int, credits: int, expires_at: datetime):
    """
    Send warning email to user about upcoming credit expiration.

    Args:
        user: User object
        days_remaining: Days until expiration
        credits: Number of credits expiring
        expires_at: Expiration date
    """
    # TODO: Implement with Resend when ready
    # from resend import Resend
    # resend = Resend(api_key=config.RESEND_API_KEY)

    logger.info(f"[EMAIL PENDING] Warning to {user.email}: {credits} credits expire in {days_remaining} days")

    # Uncomment when Resend is configured:
    """
    try:
        resend.emails.send({
            "from": "TTS Reader <noreply@ttsreader.com>",
            "to": user.email,
            "subject": f"⚠️ Your credits expire in {days_remaining} days",
            "html": f'''
                <h2>Credit Expiration Warning</h2>
                <p>Hi {user.username},</p>
                <p>You have <strong>{credits:,} credits</strong> that will expire in <strong>{days_remaining} days</strong>.</p>
                <p>Expiration Date: <strong>{expires_at.strftime("%B %d, %Y")}</strong></p>
                <p>Use your credits before they expire to get the most out of your purchase!</p>
                <p>Login to your account to start using your credits: <a href="https://ttsreader.com/login">TTS Reader</a></p>
                <br>
                <p>Thanks,<br>TTS Reader Team</p>
            '''
        })
        logger.info(f"✅ Sent {days_remaining}-day warning email to {user.email}")
    except Exception as e:
        logger.error(f"❌ Failed to send warning email to {user.email}: {str(e)}")
    """


def send_expiration_notification_email(user: User, credits_expired: int):
    """
    Send notification email when credits have expired.

    Args:
        user: User object
        credits_expired: Number of credits that expired
    """
    # TODO: Implement with Resend when ready
    logger.info(f"[EMAIL PENDING] Expiration notice to {user.email}: {credits_expired} credits expired")

    # Uncomment when Resend is configured:
    """
    try:
        resend.emails.send({
            "from": "TTS Reader <noreply@ttsreader.com>",
            "to": user.email,
            "subject": "Your TTS credits have expired",
            "html": f'''
                <h2>Credits Expired</h2>
                <p>Hi {user.username},</p>
                <p><strong>{credits_expired:,} credits</strong> have expired from your account.</p>
                <p>These credits were purchased more than one year ago and are no longer available.</p>
                <p>Purchase new credits to continue using TTS Reader: <a href="https://ttsreader.com/pricing">View Pricing</a></p>
                <br>
                <p>Thanks,<br>TTS Reader Team</p>
            '''
        })
        logger.info(f"✅ Sent expiration notification to {user.email}")
    except Exception as e:
        logger.error(f"❌ Failed to send expiration email to {user.email}: {str(e)}")
    """


# ============ CREDIT EXPIRATION JOBS ============

def expire_old_credits(db: Session) -> Tuple[int, int]:
    """
    Find and expire credit transactions that are older than 1 year.
    Updates user tiers if necessary.

    Args:
        db: Database session

    Returns:
        Tuple[int, int]: (number of transactions expired, number of users affected)
    """
    logger.info("🔍 Checking for expired credit transactions...")

    # Find all ACTIVE transactions that have passed their expiration date
    now = datetime.utcnow()
    expired_transactions = db.query(CreditTransaction).filter(
        and_(
            CreditTransaction.status == TransactionStatus.ACTIVE,
            CreditTransaction.expires_at <= now
        )
    ).all()

    if not expired_transactions:
        logger.info("✅ No expired transactions found")
        return 0, 0

    users_affected = set()
    total_expired = 0

    for transaction in expired_transactions:
        # Mark transaction as expired
        credits_lost = transaction.credits_remaining
        transaction.credits_remaining = 0
        transaction.status = TransactionStatus.EXPIRED
        transaction.updated_at = now

        users_affected.add(transaction.user_id)
        total_expired += 1

        logger.info(
            f"⏰ Expired transaction {transaction.id}: "
            f"User {transaction.user.username} lost {credits_lost} credits"
        )

        # Send expiration notification email
        send_expiration_notification_email(transaction.user, credits_lost)

    # Update affected users' cached balances and tiers
    for user_id in users_affected:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user:
            user.sync_credit_balance()
            user.update_tier_from_credits()
            logger.info(
                f"👤 Updated user {user.username}: "
                f"{user.credit_balance} credits remaining, tier: {user.tier.value}"
            )

    db.commit()
    logger.info(f"✅ Expired {total_expired} transactions affecting {len(users_affected)} users")

    return total_expired, len(users_affected)


def send_expiration_warnings(db: Session) -> Tuple[int, int]:
    """
    Send warning emails for credits expiring soon.
    Sends warnings at 30 days and 7 days before expiration.

    Args:
        db: Database session

    Returns:
        Tuple[int, int]: (30-day warnings sent, 7-day warnings sent)
    """
    logger.info("📧 Checking for upcoming credit expirations...")

    now = datetime.utcnow()
    thirty_days_from_now = now + timedelta(days=30)
    seven_days_from_now = now + timedelta(days=7)

    # 30-day warning window (29-31 days from now)
    thirty_day_window_start = now + timedelta(days=29)
    thirty_day_window_end = now + timedelta(days=31)

    # 7-day warning window (6-8 days from now)
    seven_day_window_start = now + timedelta(days=6)
    seven_day_window_end = now + timedelta(days=8)

    # Find transactions expiring in ~30 days
    thirty_day_warnings = db.query(CreditTransaction).filter(
        and_(
            CreditTransaction.status == TransactionStatus.ACTIVE,
            CreditTransaction.expires_at >= thirty_day_window_start,
            CreditTransaction.expires_at <= thirty_day_window_end,
            CreditTransaction.credits_remaining > 0
        )
    ).all()

    # Find transactions expiring in ~7 days
    seven_day_warnings = db.query(CreditTransaction).filter(
        and_(
            CreditTransaction.status == TransactionStatus.ACTIVE,
            CreditTransaction.expires_at >= seven_day_window_start,
            CreditTransaction.expires_at <= seven_day_window_end,
            CreditTransaction.credits_remaining > 0
        )
    ).all()

    thirty_day_count = 0
    for transaction in thirty_day_warnings:
        days_remaining = (transaction.expires_at - now).days
        send_expiration_warning_email(
            transaction.user,
            days_remaining,
            transaction.credits_remaining,
            transaction.expires_at
        )
        thirty_day_count += 1

    seven_day_count = 0
    for transaction in seven_day_warnings:
        days_remaining = (transaction.expires_at - now).days
        send_expiration_warning_email(
            transaction.user,
            days_remaining,
            transaction.credits_remaining,
            transaction.expires_at
        )
        seven_day_count += 1

    logger.info(f"✅ Sent {thirty_day_count} 30-day warnings and {seven_day_count} 7-day warnings")

    return thirty_day_count, seven_day_count


# ============ MAIN JOB RUNNER ============

def run_daily_jobs():
    """
    Run all daily background jobs:
    1. Expire old credits
    2. Send expiration warnings

    This should be run once per day via cron or scheduler.
    """
    logger.info("=" * 60)
    logger.info("🚀 Starting daily credit expiration jobs")
    logger.info("=" * 60)

    db = get_db_session()

    try:
        # Expire old credits
        expired_count, users_affected = expire_old_credits(db)

        # Send warnings
        thirty_day_warnings, seven_day_warnings = send_expiration_warnings(db)

        logger.info("=" * 60)
        logger.info("✅ Daily jobs completed successfully")
        logger.info(f"   - Expired: {expired_count} transactions ({users_affected} users)")
        logger.info(f"   - Warnings: {thirty_day_warnings} (30-day), {seven_day_warnings} (7-day)")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ Error running daily jobs: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    """
    Run this script directly for testing or via cron.

    Example crontab entry (run daily at 2 AM):
    0 2 * * * cd /path/to/tts-reader-aws-backend && python -m app.background_jobs

    Or use a Python scheduler like APScheduler:
    from apscheduler.schedulers.blocking import BlockingScheduler
    scheduler = BlockingScheduler()
    scheduler.add_job(run_daily_jobs, 'cron', hour=2)
    scheduler.start()
    """
    run_daily_jobs()
