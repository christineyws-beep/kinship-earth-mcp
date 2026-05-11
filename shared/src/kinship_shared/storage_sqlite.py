"""
SQLite-backed conversation store for local development.

Stores conversation turns in ~/.kinship-earth/conversations.db
(configurable via KINSHIP_DB_PATH environment variable).
"""

from __future__ import annotations

import json
import logging
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from .storage import ConversationStore, ConversationTurn

logger = logging.getLogger(__name__)

_DEFAULT_DB_DIR = Path.home() / ".kinship-earth"
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "conversations.db"

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS turns (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    user_id TEXT,
    timestamp TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    tool_params TEXT NOT NULL,
    tool_result_summary TEXT NOT NULL,
    lat REAL,
    lng REAL,
    taxa_mentioned TEXT NOT NULL,
    feedback TEXT,
    feedback_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_turns_conversation ON turns(conversation_id);
CREATE INDEX IF NOT EXISTS idx_turns_tool ON turns(tool_name);
CREATE INDEX IF NOT EXISTS idx_turns_lat_lng ON turns(lat, lng);
CREATE INDEX IF NOT EXISTS idx_turns_timestamp ON turns(timestamp DESC);
"""


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Approximate distance in km between two lat/lng points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _row_to_turn(row: aiosqlite.Row) -> ConversationTurn:
    """Convert a SQLite row to a ConversationTurn."""
    return ConversationTurn(
        id=row[0],
        conversation_id=row[1],
        user_id=row[2],
        timestamp=datetime.fromisoformat(row[3]),
        tool_name=row[4],
        tool_params=json.loads(row[5]),
        tool_result_summary=json.loads(row[6]),
        lat=row[7],
        lng=row[8],
        taxa_mentioned=json.loads(row[9]),
        feedback=row[10],
        feedback_at=datetime.fromisoformat(row[11]) if row[11] else None,
    )


class SQLiteConversationStore(ConversationStore):
    """Async SQLite conversation store."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or os.environ.get(
            "KINSHIP_DB_PATH", str(_DEFAULT_DB_PATH)
        )

    async def initialize(self) -> None:
        """Create database directory and tables."""
        db_dir = Path(self._db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(_CREATE_TABLES)
            await db.commit()

    async def store_turn(self, turn: ConversationTurn) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO turns
                (id, conversation_id, user_id, timestamp, tool_name,
                 tool_params, tool_result_summary, lat, lng,
                 taxa_mentioned, feedback, feedback_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn.id,
                    turn.conversation_id,
                    turn.user_id,
                    turn.timestamp.isoformat(),
                    turn.tool_name,
                    json.dumps(turn.tool_params),
                    json.dumps(turn.tool_result_summary),
                    turn.lat,
                    turn.lng,
                    json.dumps(turn.taxa_mentioned),
                    turn.feedback,
                    turn.feedback_at.isoformat() if turn.feedback_at else None,
                ),
            )
            await db.commit()

    async def get_conversation(self, conversation_id: str) -> list[ConversationTurn]:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM turns WHERE conversation_id = ? ORDER BY timestamp",
                (conversation_id,),
            )
            rows = await cursor.fetchall()
            return [_row_to_turn(row) for row in rows]

    async def get_turns_by_location(
        self, lat: float, lng: float, radius_km: float, limit: int = 50,
    ) -> list[ConversationTurn]:
        # Use a bounding box for rough filtering, then haversine for precision
        lat_delta = radius_km / 111.0  # ~111km per degree latitude
        lng_delta = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))

        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                SELECT * FROM turns
                WHERE lat IS NOT NULL AND lng IS NOT NULL
                  AND lat BETWEEN ? AND ?
                  AND lng BETWEEN ? AND ?
                ORDER BY timestamp DESC
                """,
                (lat - lat_delta, lat + lat_delta, lng - lng_delta, lng + lng_delta),
            )
            rows = await cursor.fetchall()

        # Precise haversine filter
        turns = []
        for row in rows:
            turn = _row_to_turn(row)
            if turn.lat is not None and turn.lng is not None:
                dist = _haversine_km(lat, lng, turn.lat, turn.lng)
                if dist <= radius_km:
                    turns.append(turn)
            if len(turns) >= limit:
                break

        return turns

    async def get_turns_by_taxon(
        self, scientific_name: str, limit: int = 50,
    ) -> list[ConversationTurn]:
        search_term = scientific_name.lower()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                SELECT * FROM turns
                WHERE LOWER(taxa_mentioned) LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (f"%{search_term}%", limit),
            )
            rows = await cursor.fetchall()
            return [_row_to_turn(row) for row in rows]

    async def add_feedback(self, turn_id: str, feedback: str) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                UPDATE turns SET feedback = ?, feedback_at = ?
                WHERE id = ?
                """,
                (feedback, datetime.now(tz=timezone.utc).isoformat(), turn_id),
            )
            await db.commit()
            return cursor.rowcount > 0
