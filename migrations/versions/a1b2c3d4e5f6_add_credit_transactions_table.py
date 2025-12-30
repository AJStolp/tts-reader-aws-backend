"""add_credit_transactions_table

Revision ID: a1b2c3d4e5f6
Revises: 05cf6f12d158
Create Date: 2025-12-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '05cf6f12d158'
branch_labels = None
depends_on = None


def upgrade():
    # Create transactionstatus enum
    op.execute("CREATE TYPE transactionstatus AS ENUM ('ACTIVE', 'EXPIRED', 'CONSUMED')")

    # Create credit_transactions table
    op.create_table(
        'credit_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('credits_purchased', sa.Integer(), nullable=False),
        sa.Column('credits_remaining', sa.Integer(), nullable=False),
        sa.Column('purchase_price', sa.Integer(), nullable=True),
        sa.Column('tier_at_purchase', sa.String(20), nullable=True),  # Store as string to avoid enum issues
        sa.Column('purchased_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),  # Store as string initially
        sa.Column('stripe_payment_id', sa.String(128), nullable=True),
        sa.Column('stripe_session_id', sa.String(128), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE')
    )

    # Alter status column to use the enum type
    op.execute("ALTER TABLE credit_transactions ALTER COLUMN status TYPE transactionstatus USING status::transactionstatus")

    # Create indexes for better query performance
    op.create_index('ix_credit_transactions_user_id', 'credit_transactions', ['user_id'])
    op.create_index('ix_credit_transactions_status', 'credit_transactions', ['status'])
    op.create_index('ix_credit_transactions_expires_at', 'credit_transactions', ['expires_at'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_credit_transactions_expires_at', 'credit_transactions')
    op.drop_index('ix_credit_transactions_status', 'credit_transactions')
    op.drop_index('ix_credit_transactions_user_id', 'credit_transactions')

    # Drop table
    op.drop_table('credit_transactions')

    # Drop custom enums
    op.execute('DROP TYPE IF EXISTS transactionstatus')
