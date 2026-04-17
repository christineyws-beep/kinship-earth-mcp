"""
Conversation storage schema and abstract interface.

Every MCP tool invocation can be stored as a ConversationTurn for:
- Building the ecological knowledge graph (Phase 4)
- User history and query replay
- Feedback capture for quality improvement
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from .schema import Location


class ConversationTurn(BaseModel):
    """A single tool invocation and its result summary."""

    id: str = Field(description="UUID for this turn")
    conversation_id: str = Field(description="Groups turns into a session")
    user_id: Optional[str] = Field(default=None, description="User identity (None if unauthenticated)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    tool_name: str = Field(description="MCP tool that was called, e.g. 'ecology_search'")
    tool_params: dict = Field(default_factory=dict, description="Input parameters to the tool")
    tool_result_summary: dict = Field(default_factory=dict, description="Condensed result (not full payload)")
    lat: Optional[float] = Field(default=None, description="Latitude extracted from params")
    lng: Optional[float] = Field(default=None, description="Longitude extracted from params")
    taxa_mentioned: list[str] = Field(default_factory=list, description="Scientific names from params/results")
    feedback: Optional[str] = Field(default=None, description="User feedback: 'helpful', 'not_helpful', or free text")
    feedback_at: Optional[datetime] = Field(default=None)


class ConversationStore(ABC):
    """Abstract interface for conversation persistence.

    Implementations: SQLiteConversationStore (dev), future Supabase (prod).
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Create tables and indexes if they don't exist."""
        ...

    @abstractmethod
    async def store_turn(self, turn: ConversationTurn) -> None:
        """Persist a conversation turn."""
        ...

    @abstractmethod
    async def get_conversation(self, conversation_id: str) -> list[ConversationTurn]:
        """Get all turns in a conversation, ordered by timestamp."""
        ...

    @abstractmethod
    async def get_turns_by_location(
        self, lat: float, lng: float, radius_km: float, limit: int = 50,
    ) -> list[ConversationTurn]:
        """Find turns near a geographic location."""
        ...

    @abstractmethod
    async def get_turns_by_taxon(
        self, scientific_name: str, limit: int = 50,
    ) -> list[ConversationTurn]:
        """Find turns that mention a species."""
        ...

    @abstractmethod
    async def add_feedback(self, turn_id: str, feedback: str) -> bool:
        """Attach feedback to a turn. Returns True if turn was found."""
        ...
