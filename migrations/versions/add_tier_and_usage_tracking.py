"""add tier and usage tracking fields

Revision ID: 5b8c9d1e2f3a
Revises: 3f3d70d2fc33
Create Date: 2025-11-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '5b8c9d1e2f3a'
down_revision = '3f3d70d2fc33'
branch_labels = None
depends_on = None


def upgrade():
    # Create enum type for PostgreSQL
    op.execute("CREATE TYPE usertier AS ENUM ('FREE', 'PREMIUM', 'PRO')")

    # Add new columns
    op.add_column('users', sa.Column('stripe_price_id', sa.String(length=128), nullable=True))
    op.add_column('users', sa.Column('tier', sa.Enum('FREE', 'PREMIUM', 'PRO', name='usertier'), nullable=False, server_default='FREE'))
    op.add_column('users', sa.Column('monthly_usage', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('usage_reset_date', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')))


def downgrade():
    op.drop_column('users', 'usage_reset_date')
    op.drop_column('users', 'monthly_usage')
    op.drop_column('users', 'tier')
    op.drop_column('users', 'stripe_price_id')
    op.execute('DROP TYPE usertier')
