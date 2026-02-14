"""
Test User Setup Script for Load Testing

Creates test user accounts with sufficient credits for load testing.
Run this before executing load tests to ensure test users exist.

Usage:
    python setup_test_users.py --count 10 --credits 100000

This script:
1. Creates test users in the database
2. Assigns them to specified tiers (FREE, PREMIUM, PRO)
3. Adds credits for TTS usage
4. Marks emails as verified (skips email verification)
"""

import asyncio
import argparse
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import bcrypt
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_CONNECTION_STRING")

if not DATABASE_URL:
    print("❌ Error: DATABASE_CONNECTION_STRING not found in .env file")
    exit(1)


def hash_password(password: str) -> str:
    """Hash password using bcrypt (matching app logic)"""
    # Truncate to 72 bytes as per app/auth.py
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')


def create_test_users(count: int, tier: str, credits: int, engine):
    """Create test user accounts with specified tier and credits"""

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        created_users = []
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        # Standard password for all test users
        password = "TestPassword123!"
        password_hash = hash_password(password)

        print(f"\n🔨 Creating {count} test users...")
        print(f"   Tier: {tier}")
        print(f"   Credits: {credits:,}")
        print(f"   Password: {password}\n")

        for i in range(count):
            email = f"loadtest_{timestamp}_{i:03d}@example.com"

            try:
                # Check if user already exists
                existing = session.execute(
                    text("SELECT user_id FROM users WHERE email = :email"),
                    {"email": email}
                ).fetchone()

                if existing:
                    print(f"⚠  User {email} already exists, skipping...")
                    continue

                # Insert user
                result = session.execute(
                    text("""
                        INSERT INTO users (
                            username, email, password_hash, tier, email_verified,
                            created_at, updated_at
                        )
                        VALUES (
                            :username, :email, :password_hash, :tier, true,
                            :created_at, :updated_at
                        )
                        RETURNING user_id
                    """),
                    {
                        "username": email.split('@')[0],  # Use email prefix as username
                        "email": email,
                        "password_hash": password_hash,
                        "tier": tier,
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                )

                user_id = result.fetchone()[0]

                # Add credits if specified
                if credits > 0:
                    session.execute(
                        text("""
                            INSERT INTO credit_transactions (
                                user_id, credits_purchased, credits_remaining,
                                purchased_at, expires_at, status, created_at
                            )
                            VALUES (
                                :user_id, :credits, :credits,
                                :purchased_at, :expires_at, 'ACTIVE', :created_at
                            )
                        """),
                        {
                            "user_id": user_id,
                            "credits": credits,
                            "purchased_at": datetime.utcnow(),
                            "expires_at": datetime.utcnow() + timedelta(days=90),
                            "created_at": datetime.utcnow()
                        }
                    )

                session.commit()
                created_users.append(email)
                print(f"✓ Created user {i+1}/{count}: {email}")

            except Exception as e:
                session.rollback()
                print(f"❌ Error creating user {email}: {str(e)}")
                continue

        print(f"\n✅ Successfully created {len(created_users)} test users")

        if created_users:
            print("\n📋 Test User Credentials:")
            print("=" * 60)
            print(f"Email Pattern: loadtest_{timestamp}_XXX@example.com")
            print(f"Password (all): {password}")
            print(f"Tier: {tier}")
            print(f"Credits: {credits:,}")
            print("=" * 60)

            # Save to file for reference
            with open(f"test_users_{timestamp}.txt", "w") as f:
                f.write("TTS Reader Load Test Users\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"Created: {datetime.now()}\n")
                f.write(f"Password (all): {password}\n")
                f.write(f"Tier: {tier}\n")
                f.write(f"Credits: {credits:,}\n\n")
                f.write("User Emails:\n")
                for email in created_users:
                    f.write(f"  - {email}\n")

            print(f"\n💾 User list saved to: test_users_{timestamp}.txt")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        session.rollback()
    finally:
        session.close()


def create_single_loadtest_user(engine):
    """Create a single persistent load test user for returning user simulations"""

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    email = "loadtest_user@example.com"
    password = "TestPassword123!"
    password_hash = hash_password(password)
    tier = "PRO"
    credits = 1000000  # 1 million credits

    try:
        # Check if exists
        existing = session.execute(
            text("SELECT user_id FROM users WHERE email = :email"),
            {"email": email}
        ).fetchone()

        if existing:
            print(f"\n✓ Persistent load test user already exists: {email}")

            # Update credits if low
            user_id = existing[0]
            current_credits = session.execute(
                text("""
                    SELECT COALESCE(SUM(amount), 0) as total
                    FROM credit_transactions
                    WHERE user_id = :user_id
                """),
                {"user_id": user_id}
            ).fetchone()[0]

            if current_credits < 100000:
                print(f"   Current credits: {current_credits:,} (low)")
                print("   Adding 1,000,000 credits...")

                session.execute(
                    text("""
                        INSERT INTO credit_transactions (
                            user_id, credits_purchased, credits_remaining,
                            purchased_at, expires_at, status, created_at
                        )
                        VALUES (
                            :user_id, :credits, :credits,
                            :purchased_at, :expires_at, 'ACTIVE', :created_at
                        )
                    """),
                    {
                        "user_id": user_id,
                        "credits": credits,
                        "purchased_at": datetime.utcnow(),
                        "expires_at": datetime.utcnow() + timedelta(days=90),
                        "created_at": datetime.utcnow()
                    }
                )
                session.commit()
                print("   ✓ Credits added")
            else:
                print(f"   Current credits: {current_credits:,} (sufficient)")

        else:
            print(f"\n🔨 Creating persistent load test user...")

            result = session.execute(
                text("""
                    INSERT INTO users (
                        username, email, password_hash, tier, email_verified,
                        created_at, updated_at
                    )
                    VALUES (
                        :username, :email, :password_hash, :tier, true,
                        :created_at, :updated_at
                    )
                    RETURNING user_id
                """),
                {
                    "username": "loadtest_user",
                    "email": email,
                    "password_hash": password_hash,
                    "tier": tier,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            )

            user_id = result.fetchone()[0]

            # Add credits
            session.execute(
                text("""
                    INSERT INTO credit_transactions (
                        user_id, credits_purchased, credits_remaining,
                        purchased_at, expires_at, status, created_at
                    )
                    VALUES (
                        :user_id, :credits, :credits,
                        :purchased_at, :expires_at, 'ACTIVE', :created_at
                    )
                """),
                {
                    "user_id": user_id,
                    "credits": credits,
                    "purchased_at": datetime.utcnow(),
                    "expires_at": datetime.utcnow() + timedelta(days=90),
                    "created_at": datetime.utcnow()
                }
            )

            session.commit()
            print(f"✓ Created user: {email}")

        print("\n📋 Persistent Load Test User:")
        print("=" * 60)
        print(f"Email: {email}")
        print(f"Password: {password}")
        print(f"Tier: {tier}")
        print(f"Use in locustfile.py for returning user logins")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        session.rollback()
    finally:
        session.close()


def cleanup_test_users(engine, pattern=None):
    """Delete test users (use with caution!)"""

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        if pattern is None:
            pattern = "loadtest_%@example.com"

        print(f"\n🗑️  Finding test users matching: {pattern}")

        # Find users
        result = session.execute(
            text("SELECT id, email FROM users WHERE email LIKE :pattern"),
            {"pattern": pattern}
        )

        users = result.fetchall()

        if not users:
            print("No test users found.")
            return

        print(f"Found {len(users)} test users:")
        for user_id, email in users:
            print(f"  - {email}")

        confirm = input("\n⚠️  Delete these users? This cannot be undone! (type 'DELETE' to confirm): ")

        if confirm != "DELETE":
            print("Cancelled.")
            return

        # Delete credit transactions first
        for user_id, email in users:
            session.execute(
                text("DELETE FROM credit_transactions WHERE user_id = :user_id"),
                {"user_id": user_id}
            )

        # Delete users (ON DELETE CASCADE should handle credit_transactions)
        session.execute(
            text("DELETE FROM users WHERE email LIKE :pattern"),
            {"pattern": pattern}
        )

        session.commit()
        print(f"\n✅ Deleted {len(users)} test users")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        session.rollback()
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Setup test users for TTS Reader load testing")

    parser.add_argument(
        '--count',
        type=int,
        default=10,
        help='Number of test users to create (default: 10)'
    )

    parser.add_argument(
        '--tier',
        type=str,
        choices=['FREE', 'PREMIUM', 'PRO'],
        default='PRO',
        help='User tier (default: PRO)'
    )

    parser.add_argument(
        '--credits',
        type=int,
        default=100000,
        help='Credits per user (default: 100,000 = 100M characters)'
    )

    parser.add_argument(
        '--persistent',
        action='store_true',
        help='Create/update persistent loadtest_user@example.com for returning user tests'
    )

    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Delete all test users (CAUTION: irreversible!)'
    )

    parser.add_argument(
        '--cleanup-pattern',
        type=str,
        help='Custom pattern for cleanup (e.g., "loadtest_20240115%")'
    )

    args = parser.parse_args()

    # Create database engine
    try:
        engine = create_engine(DATABASE_URL)
        print("✓ Connected to database")
    except Exception as e:
        print(f"❌ Failed to connect to database: {str(e)}")
        exit(1)

    # Execute requested action
    if args.cleanup:
        cleanup_test_users(engine, args.cleanup_pattern)
    elif args.persistent:
        create_single_loadtest_user(engine)
    else:
        create_test_users(args.count, args.tier, args.credits, engine)


if __name__ == "__main__":
    main()
