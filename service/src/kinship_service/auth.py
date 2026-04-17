"""
Authentication middleware.

When Supabase credentials are configured, verifies JWT bearer tokens.
Otherwise, creates anonymous users for free-tier access.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, Request

from kinship_shared import SQLiteConversationStore

from .config import settings

logger = logging.getLogger(__name__)

# Lazy-loaded Supabase client
_supabase_client = None


def _get_supabase():
    global _supabase_client
    if _supabase_client is None and settings.has_supabase:
        try:
            from supabase import create_client
            _supabase_client = create_client(settings.supabase_url, settings.supabase_key)
        except ImportError:
            logger.warning("supabase package not installed — running in anonymous mode")
    return _supabase_client


class UserContext:
    """Resolved user for the current request."""

    def __init__(
        self,
        user_id: str,
        email: str = "",
        name: str | None = None,
        tier: str = "free",
        authenticated: bool = False,
    ):
        self.user_id = user_id
        self.email = email
        self.name = name
        self.tier = tier
        self.authenticated = authenticated


async def get_current_user(request: Request) -> UserContext:
    """Extract and verify user from request.

    - If Authorization header with valid Supabase JWT: authenticated user
    - If no header or Supabase not configured: anonymous user
    """
    auth_header = request.headers.get("Authorization", "")

    if auth_header.startswith("Bearer ") and settings.has_supabase:
        token = auth_header[7:]
        client = _get_supabase()
        if client:
            try:
                user_response = client.auth.get_user(token)
                user = user_response.user
                if user:
                    return UserContext(
                        user_id=user.id,
                        email=user.email or "",
                        name=user.user_metadata.get("full_name") if user.user_metadata else None,
                        tier="free",
                        authenticated=True,
                    )
            except Exception as e:
                logger.warning("Supabase auth failed: %s", e)
                raise HTTPException(status_code=401, detail="Invalid or expired token")

    return UserContext(user_id=f"anon-{uuid.uuid4().hex[:8]}")


class RateLimiter:
    """Simple in-memory rate limiter (per-user, daily reset)."""

    def __init__(self):
        self._counts: dict[str, dict] = {}

    def check(self, user_id: str, limit: int) -> bool:
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        entry = self._counts.get(user_id)

        if entry is None or entry.get("date") != today:
            self._counts[user_id] = {"date": today, "count": 0}
            entry = self._counts[user_id]

        return entry["count"] < limit

    def increment(self, user_id: str) -> int:
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        entry = self._counts.get(user_id)

        if entry is None or entry.get("date") != today:
            self._counts[user_id] = {"date": today, "count": 0}
            entry = self._counts[user_id]

        entry["count"] += 1
        return entry["count"]

    def get_usage(self, user_id: str) -> int:
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        entry = self._counts.get(user_id)
        if entry and entry.get("date") == today:
            return entry["count"]
        return 0


rate_limiter = RateLimiter()
