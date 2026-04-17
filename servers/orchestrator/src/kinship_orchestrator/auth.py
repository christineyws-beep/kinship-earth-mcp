"""
User authentication and identity management.

Provides user identity for conversation tracking, rate limiting,
and BYOK API key storage. Disabled by default — opt-in via
KINSHIP_AUTH_ENABLED=true.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class User(BaseModel):
    """A Kinship Earth user."""

    id: str
    email: str = ""
    name: Optional[str] = None
    provider: str = "anonymous"  # "github" | "google" | "anonymous"
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    api_keys: dict[str, str] = Field(default_factory=dict, description="BYOK keys: {'ebird': 'key...'}")
    tier: str = "free"  # "free" | "pro"
    queries_today: int = 0
    queries_limit: int = 50  # Daily limit for free tier
    last_query_date: Optional[str] = None  # YYYY-MM-DD of last query


class AuthManager(ABC):
    """Abstract interface for user authentication."""

    @abstractmethod
    async def initialize(self) -> None:
        """Create tables if needed."""
        ...

    @abstractmethod
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        ...

    @abstractmethod
    async def create_anonymous_user(self) -> User:
        """Create an anonymous user for unauthenticated access."""
        ...

    @abstractmethod
    async def check_rate_limit(self, user: User) -> bool:
        """Returns True if user has queries remaining today."""
        ...

    @abstractmethod
    async def increment_usage(self, user: User) -> None:
        """Increment the user's daily query count."""
        ...

    @abstractmethod
    async def set_api_key(self, user_id: str, service: str, api_key: str) -> None:
        """Store a BYOK API key for a user."""
        ...

    @abstractmethod
    async def get_api_keys(self, user_id: str) -> dict[str, str]:
        """Get all BYOK API keys for a user (service -> key)."""
        ...
