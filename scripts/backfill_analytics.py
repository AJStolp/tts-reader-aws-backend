"""
One-time backfill script to seed analytics data from existing records.
Run after the b2c3d4e5f6a7 migration.

Backfills:
- platform_stats.total_users from users table
- users.total_lifetime_spend from credit_transactions
- users.purchase_count from credit_transactions
- users.first_purchase_at from credit_transactions
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from sqlalchemy import func
from database import SessionLocal
from models import User, CreditTransaction, PlatformStats, TransactionStatus


def backfill():
    db = SessionLocal()
    try:
        print("Starting analytics backfill...")

        # 1. Backfill platform_stats.total_users
        total_users = db.query(func.count(User.user_id)).scalar() or 0
        stat = db.query(PlatformStats).filter_by(stat_key="total_users").first()
        if stat:
            stat.stat_value = total_users
            stat.updated_at = datetime.utcnow()
        print(f"  total_users: {total_users}")

        # 2. Backfill per-user LTV fields from credit_transactions
        users_with_purchases = db.query(
            CreditTransaction.user_id,
            func.count(CreditTransaction.id).label("purchase_count"),
            func.coalesce(func.sum(CreditTransaction.purchase_price), 0).label("total_spend"),
            func.min(CreditTransaction.purchased_at).label("first_purchase"),
        ).group_by(CreditTransaction.user_id).all()

        updated_count = 0
        for row in users_with_purchases:
            user = db.query(User).filter(User.user_id == row.user_id).first()
            if user:
                user.purchase_count = row.purchase_count
                user.total_lifetime_spend = row.total_spend or 0
                user.first_purchase_at = row.first_purchase
                updated_count += 1

        print(f"  Backfilled LTV data for {updated_count} users with purchases")

        # 3. Set last_active_at from last_login for all users
        users_with_login = db.query(User).filter(User.last_login.isnot(None)).all()
        for user in users_with_login:
            if not user.last_active_at:
                user.last_active_at = user.last_login

        print(f"  Set last_active_at for {len(users_with_login)} users from last_login")

        db.commit()
        print("Backfill complete!")

    except Exception as e:
        db.rollback()
        print(f"Backfill failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    backfill()
