"""
Analytics helper functions for KPI / marketing data collection.
Records usage events, lifecycle milestones, and platform-wide stats.
"""
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from models import (
    User, UsageEvent, UsageEventType, LifecycleEvent,
    LifecycleEventName, PlatformStats
)

logger = logging.getLogger(__name__)


def extract_domain(url: str) -> Optional[str]:
    """Extract domain from URL for source_domain tracking."""
    try:
        return urlparse(url).netloc or None
    except Exception:
        return None


def increment_platform_stat(db: Session, stat_key: str, increment: int = 1) -> None:
    """Increment a platform stat counter. Creates the row if it doesn't exist."""
    stat = db.query(PlatformStats).filter_by(stat_key=stat_key).first()
    if stat:
        stat.stat_value += increment
        stat.updated_at = datetime.utcnow()
    else:
        stat = PlatformStats(stat_key=stat_key, stat_value=increment)
        db.add(stat)


def record_usage_event(
    db: Session,
    user: User,
    event_type: UsageEventType,
    char_count: int,
    credits_consumed: int = 0,
    voice_id: str = None,
    engine: str = None,
    source_url: str = None,
    content_type: str = None,
    extraction_method: str = None,
    duration_ms: int = None,
) -> UsageEvent:
    """Record a usage event and update per-user + platform-wide counters."""
    event = UsageEvent(
        user_id=user.user_id,
        event_type=event_type,
        char_count=char_count,
        credits_consumed=credits_consumed,
        voice_id=voice_id,
        engine=engine,
        source_domain=extract_domain(source_url) if source_url else None,
        content_type=content_type,
        extraction_method=extraction_method,
        duration_ms=duration_ms,
    )
    db.add(event)

    # Update per-user lifetime counters
    if event_type == UsageEventType.SYNTHESIZE:
        user.total_chars_synthesized = (user.total_chars_synthesized or 0) + char_count
        increment_platform_stat(db, "total_characters_synthesized", char_count)
        increment_platform_stat(db, "total_syntheses", 1)
    elif event_type == UsageEventType.EXTRACT:
        user.total_chars_extracted = (user.total_chars_extracted or 0) + char_count
        increment_platform_stat(db, "total_characters_extracted", char_count)
        increment_platform_stat(db, "total_extractions", 1)

    # Update last_active_at
    user.last_active_at = datetime.utcnow()

    # Check for first-time lifecycle events
    _check_first_time_events(db, user, event_type)

    return event


def _check_first_time_events(db: Session, user: User, event_type: UsageEventType) -> None:
    """Emit lifecycle events for first-time actions."""
    if event_type == UsageEventType.SYNTHESIZE:
        existing = db.query(LifecycleEvent).filter_by(
            user_id=user.user_id,
            event_name=LifecycleEventName.FIRST_SYNTHESIS
        ).first()
        if not existing:
            record_lifecycle_event(db, user, LifecycleEventName.FIRST_SYNTHESIS)
    elif event_type == UsageEventType.EXTRACT:
        existing = db.query(LifecycleEvent).filter_by(
            user_id=user.user_id,
            event_name=LifecycleEventName.FIRST_EXTRACTION
        ).first()
        if not existing:
            record_lifecycle_event(db, user, LifecycleEventName.FIRST_EXTRACTION)


def record_lifecycle_event(
    db: Session,
    user: User,
    event_name: LifecycleEventName,
    metadata: dict = None,
) -> LifecycleEvent:
    """Record a lifecycle funnel event."""
    event = LifecycleEvent(
        user_id=user.user_id,
        event_name=event_name,
        metadata_json=metadata,
    )
    db.add(event)
    logger.info(f"Lifecycle event: {event_name.value} for user {user.username}")
    return event


def record_purchase_lifecycle(
    db: Session,
    user: User,
    amount_cents: int,
    credits: int,
    stripe_session_id: str = None,
) -> None:
    """Update user LTV fields and emit purchase lifecycle events."""
    user.purchase_count = (user.purchase_count or 0) + 1
    user.total_lifetime_spend = (user.total_lifetime_spend or 0) + amount_cents

    if user.purchase_count == 1:
        user.first_purchase_at = datetime.utcnow()
        record_lifecycle_event(db, user, LifecycleEventName.FIRST_PURCHASE, {
            "amount_cents": amount_cents,
            "credits": credits,
            "stripe_session_id": stripe_session_id,
        })
    elif user.purchase_count == 2:
        record_lifecycle_event(db, user, LifecycleEventName.SECOND_PURCHASE, {
            "amount_cents": amount_cents,
            "credits": credits,
        })


def get_platform_stats(db: Session) -> dict:
    """Retrieve all platform stats as a dictionary for the public endpoint."""
    rows = db.query(PlatformStats).all()
    stats = {row.stat_key: row.stat_value for row in rows}
    listening_seconds = stats.get("total_listening_hours_seconds", 0)
    return {
        "total_characters_synthesized": stats.get("total_characters_synthesized", 0),
        "total_characters_extracted": stats.get("total_characters_extracted", 0),
        "total_extractions": stats.get("total_extractions", 0),
        "total_syntheses": stats.get("total_syntheses", 0),
        "total_users": stats.get("total_users", 0),
        "total_listening_hours": round(listening_seconds / 3600, 1) if listening_seconds else 0.0,
    }
