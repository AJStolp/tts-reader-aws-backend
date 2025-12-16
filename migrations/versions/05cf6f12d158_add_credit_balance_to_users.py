"""add_credit_balance_to_users

Revision ID: 05cf6f12d158
Revises: 5b8c9d1e2f3a
Create Date: 2025-12-15 20:39:43.577409

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '05cf6f12d158'
down_revision = '5b8c9d1e2f3a'
branch_labels = None
depends_on = None


def upgrade():
    # Add credit_balance column (1 credit = 1,000 characters)
    op.add_column('users', sa.Column('credit_balance', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    # Remove credit_balance column
    op.drop_column('users', 'credit_balance')
