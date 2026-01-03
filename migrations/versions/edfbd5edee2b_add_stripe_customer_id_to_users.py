"""add_stripe_customer_id_to_users

Revision ID: edfbd5edee2b
Revises: a1b2c3d4e5f6
Create Date: 2026-01-02 19:37:48.396494

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'edfbd5edee2b'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Add stripe_customer_id column to users table
    op.add_column('users', sa.Column('stripe_customer_id', sa.String(length=128), nullable=True))


def downgrade():
    # Remove stripe_customer_id column from users table
    op.drop_column('users', 'stripe_customer_id')
