"""add_analytics_tables_and_user_columns

Revision ID: b2c3d4e5f6a7
Revises: f7a8b9c0d1e2
Create Date: 2026-02-12 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    # Create enums
    op.execute("CREATE TYPE usageeventtype AS ENUM ('SYNTHESIZE', 'EXTRACT', 'PREVIEW', 'DOWNLOAD')")
    op.execute("CREATE TYPE lifecycleeventname AS ENUM ('REGISTERED', 'EMAIL_VERIFIED', 'FIRST_EXTRACTION', 'FIRST_SYNTHESIS', 'FIRST_PURCHASE', 'SECOND_PURCHASE', 'TIER_UPGRADE', 'TIER_DOWNGRADE', 'CHURNED', 'REACTIVATED')")

    # Create usage_events table
    op.create_table(
        'usage_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(20), nullable=False),
        sa.Column('char_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('credits_consumed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('voice_id', sa.String(50), nullable=True),
        sa.Column('engine', sa.String(20), nullable=True),
        sa.Column('source_domain', sa.String(256), nullable=True),
        sa.Column('content_type', sa.String(64), nullable=True),
        sa.Column('extraction_method', sa.String(64), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE')
    )
    op.execute("ALTER TABLE usage_events ALTER COLUMN event_type TYPE usageeventtype USING event_type::usageeventtype")
    op.create_index('ix_usage_events_user_id', 'usage_events', ['user_id'])
    op.create_index('ix_usage_events_event_type', 'usage_events', ['event_type'])
    op.create_index('ix_usage_events_created_at', 'usage_events', ['created_at'])

    # Create lifecycle_events table
    op.create_table(
        'lifecycle_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('event_name', sa.String(30), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE')
    )
    op.execute("ALTER TABLE lifecycle_events ALTER COLUMN event_name TYPE lifecycleeventname USING event_name::lifecycleeventname")
    op.create_index('ix_lifecycle_events_user_id', 'lifecycle_events', ['user_id'])
    op.create_index('ix_lifecycle_events_event_name', 'lifecycle_events', ['event_name'])
    op.create_index('ix_lifecycle_events_created_at', 'lifecycle_events', ['created_at'])

    # Create platform_stats table
    op.create_table(
        'platform_stats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('stat_key', sa.String(128), nullable=False),
        sa.Column('stat_value', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stat_key')
    )
    op.create_index('ix_platform_stats_stat_key', 'platform_stats', ['stat_key'])

    # Add new columns to users table
    # Attribution / UTM tracking
    op.add_column('users', sa.Column('signup_source', sa.String(128), nullable=True))
    op.add_column('users', sa.Column('utm_source', sa.String(128), nullable=True))
    op.add_column('users', sa.Column('utm_medium', sa.String(128), nullable=True))
    op.add_column('users', sa.Column('utm_campaign', sa.String(128), nullable=True))
    op.add_column('users', sa.Column('referred_by_user_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_users_referred_by', 'users', 'users', ['referred_by_user_id'], ['user_id'])

    # Revenue / LTV cached fields
    op.add_column('users', sa.Column('first_purchase_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('total_lifetime_spend', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('purchase_count', sa.Integer(), nullable=False, server_default='0'))

    # Activity tracking
    op.add_column('users', sa.Column('last_active_at', sa.DateTime(), nullable=True))

    # Per-user lifetime character counters
    op.add_column('users', sa.Column('total_chars_synthesized', sa.BigInteger(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('total_chars_extracted', sa.BigInteger(), nullable=False, server_default='0'))

    # Seed platform_stats with initial rows
    op.execute("""
        INSERT INTO platform_stats (stat_key, stat_value, updated_at)
        VALUES
            ('total_characters_synthesized', 0, NOW()),
            ('total_characters_extracted', 0, NOW()),
            ('total_extractions', 0, NOW()),
            ('total_syntheses', 0, NOW()),
            ('total_users', 0, NOW()),
            ('total_listening_hours_seconds', 0, NOW())
    """)


def downgrade():
    # Drop new user columns
    op.drop_column('users', 'total_chars_extracted')
    op.drop_column('users', 'total_chars_synthesized')
    op.drop_column('users', 'last_active_at')
    op.drop_column('users', 'purchase_count')
    op.drop_column('users', 'total_lifetime_spend')
    op.drop_column('users', 'first_purchase_at')
    op.drop_constraint('fk_users_referred_by', 'users', type_='foreignkey')
    op.drop_column('users', 'referred_by_user_id')
    op.drop_column('users', 'utm_campaign')
    op.drop_column('users', 'utm_medium')
    op.drop_column('users', 'utm_source')
    op.drop_column('users', 'signup_source')

    # Drop tables
    op.drop_index('ix_platform_stats_stat_key', 'platform_stats')
    op.drop_table('platform_stats')

    op.drop_index('ix_lifecycle_events_created_at', 'lifecycle_events')
    op.drop_index('ix_lifecycle_events_event_name', 'lifecycle_events')
    op.drop_index('ix_lifecycle_events_user_id', 'lifecycle_events')
    op.drop_table('lifecycle_events')

    op.drop_index('ix_usage_events_created_at', 'usage_events')
    op.drop_index('ix_usage_events_event_type', 'usage_events')
    op.drop_index('ix_usage_events_user_id', 'usage_events')
    op.drop_table('usage_events')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS lifecycleeventname")
    op.execute("DROP TYPE IF EXISTS usageeventtype")
