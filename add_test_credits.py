"""
Quick script to add test credit transactions for existing users.
Run this once to populate the credit_transactions table with test data.
"""

from datetime import datetime, timedelta
from database import SessionLocal
from models import User, CreditTransaction, TransactionStatus

def add_test_credits():
    db = SessionLocal()

    try:
        # Get all users
        users = db.query(User).all()

        if not users:
            print("No users found in database!")
            return

        print(f"Found {len(users)} users")

        for user in users:
            # Skip if user already has transactions
            existing = db.query(CreditTransaction).filter(
                CreditTransaction.user_id == user.user_id
            ).count()

            if existing > 0:
                print(f"⏭️  User {user.username} already has {existing} transactions, skipping")
                continue

            # Create test transaction with credits
            print(f"\n👤 Creating test transaction for {user.username}...")

            # Use their existing credit_balance or give them 5000 test credits
            credits_to_add = user.credit_balance if user.credit_balance > 0 else 5000

            # Create transaction using the User model method
            transaction = user.purchase_credits(
                credit_amount=credits_to_add,
                purchase_price=credits_to_add * 1,  # $0.01 per credit = credits * 1 cent
                stripe_payment_id=f"test_payment_{user.username}",
                stripe_session_id=f"test_session_{user.username}"
            )

            print(f"✅ Created transaction:")
            print(f"   - Credits: {transaction.credits_purchased}")
            print(f"   - Expires: {transaction.expires_at.date()}")
            print(f"   - Days until expiration: {transaction.days_until_expiration()}")
            print(f"   - New tier: {user.tier.value}")

        # Commit all changes
        db.commit()
        print("\n" + "="*60)
        print("✅ All test transactions created successfully!")
        print("="*60)

        # Show summary
        print("\nSummary:")
        for user in users:
            user_stats = user.get_credit_stats()
            print(f"\n👤 {user.username}:")
            print(f"   Total Credits: {user_stats['credit_balance']}")
            print(f"   Tier: {user_stats['tier']}")
            print(f"   Next Expiration: {user_stats['next_expiration']}")
            print(f"   Days Until Expiration: {user_stats['days_until_expiration']}")
            print(f"   Active Transactions: {user_stats['total_transactions']}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("="*60)
    print("Adding Test Credit Transactions")
    print("="*60)
    add_test_credits()
