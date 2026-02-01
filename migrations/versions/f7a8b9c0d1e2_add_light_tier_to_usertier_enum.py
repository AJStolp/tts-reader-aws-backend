"""add_light_tier_to_usertier_enum

Revision ID: f7a8b9c0d1e2
Revises: edfbd5edee2b
Create Date: 2026-01-31 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7a8b9c0d1e2'
down_revision = 'edfbd5edee2b'
branch_labels = None
depends_on = None


def upgrade():
    # Add LIGHT to the usertier enum in PostgreSQL
    # The AFTER clause positions it between FREE and PREMIUM
    op.execute("ALTER TYPE usertier ADD VALUE 'LIGHT' AFTER 'FREE'")


def downgrade():
    # PostgreSQL doesn't support removing enum values directly
    # We would need to recreate the enum type, which is complex
    # For safety, we just log a warning
    print("WARNING: Cannot remove LIGHT from usertier enum. Manual intervention required if needed.")
