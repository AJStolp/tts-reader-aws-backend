"""
Dittofeed event tracking service for user lifecycle and engagement analytics.

Integrates with self-hosted Dittofeed instance via its Segment-compatible REST API.
All calls are fire-and-forget to avoid blocking request handlers.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from .config import config

logger = logging.getLogger(__name__)


class DittofeedService:
    """
    Async client for Dittofeed's Segment-compatible REST API.

    All public methods are designed to be called via fire_and_forget()
    for non-blocking behavior. Errors are logged but never raised.
    """

    def __init__(self):
        self._base_url: str = config.DITTOFEED_API_BASE.rstrip("/")
        self._write_key: str = config.DITTOFEED_WRITE_KEY
        self._enabled: bool = bool(self._write_key and self._base_url)
        self._timeout: float = 5.0

        if not self._enabled:
            logger.warning(
                "Dittofeed integration disabled: "
                "DITTOFEED_WRITE_KEY or DITTOFEED_API_BASE not configured"
            )
        else:
            logger.info(f"Dittofeed integration enabled: {self._base_url}")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": self._write_key,  # Key already includes auth type prefix (e.g., "Basic ...")
            "Content-Type": "application/json",
        }

    async def _post(self, endpoint: str, payload: Dict[str, Any]) -> None:
        if not self._enabled:
            return

        url = f"{self._base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload, headers=self._headers())

                if response.status_code == 204:
                    logger.debug(
                        f"Dittofeed {endpoint}: success for user {payload.get('userId', 'unknown')}"
                    )
                elif response.status_code == 401:
                    logger.error("Dittofeed auth failed (401): check DITTOFEED_WRITE_KEY")
                else:
                    logger.warning(
                        f"Dittofeed {endpoint} unexpected status {response.status_code}: "
                        f"{response.text[:200]}"
                    )
        except httpx.TimeoutException:
            logger.warning(f"Dittofeed {endpoint} timed out for user {payload.get('userId', 'unknown')}")
        except Exception as exc:
            logger.error(f"Dittofeed {endpoint} error: {type(exc).__name__}: {exc}")

    async def identify(self, user_id: str, traits: Dict[str, Any]) -> None:
        """Send an identify event to Dittofeed with user traits."""
        payload = {
            "userId": user_id,
            "messageId": str(uuid.uuid4()),
            "traits": traits,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self._post("/api/public/apps/identify", payload)

    async def track(
        self, user_id: str, event: str, properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send a track event to Dittofeed."""
        payload = {
            "userId": user_id,
            "messageId": str(uuid.uuid4()),
            "event": event,
            "properties": properties or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self._post("/api/public/apps/track", payload)


def fire_and_forget(coro):
    """
    Schedule a coroutine as a background task without blocking.

    In FastAPI request context: uses the running event loop.
    In sync context (e.g. background_jobs.py cron): falls back to asyncio.run().
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        try:
            asyncio.run(asyncio.wait_for(coro, timeout=5.0))
        except Exception as exc:
            logger.error(f"Dittofeed fire_and_forget sync fallback error: {exc}")


# Module-level singleton
dittofeed_service = DittofeedService()
