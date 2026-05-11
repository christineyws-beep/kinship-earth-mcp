"""
SQLite-backed user store for local development.

Database at ~/.kinship-earth/users.db (configurable via KINSHIP_USERS_DB_PATH).
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite

from .auth import AuthManager, User

logger = logging.getLogger(__name__)

_DEFAULT_DB_DIR = Path.home() / ".kinship-earth"
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "users.db"

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL DEFAULT '',
    name TEXT,
    provider TEXT NOT NULL DEFAULT 'anonymous',
    created_at TEXT NOT NULL,
    api_keys TEXT NOT NULL DEFAULT '{}',
    tier TEXT NOT NULL DEFAULT 'free',
    queries_today INTEGER NOT NULL DEFAULT 0,
    queries_limit INTEGER NOT NULL DEFAULT 50,
    last_query_date TEXT
);
"""


class SQLiteAuthManager(AuthManager):
    """Async SQLite user store for local development."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or os.environ.get(
            "KINSHIP_USERS_DB_PATH", str(_DEFAULT_DB_PATH)
        )

    async def initialize(self) -> None:
        db_dir = Path(self._db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(_CREATE_TABLES)
            await db.commit()

    async def get_user(self, user_id: str) -> Optional[User]:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_user(row)

    async def create_anonymous_user(self) -> User:
        user = User(
            id=str(uuid.uuid4()),
            provider="anonymous",
            created_at=datetime.now(tz=timezone.utc),
        )
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO users (id, email, name, provider, created_at, api_keys, tier, queries_today, queries_limit, last_query_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.id, user.email, user.name, user.provider,
                    user.created_at.isoformat(), json.dumps(user.api_keys),
                    user.tier, user.queries_today, user.queries_limit,
                    user.last_query_date,
                ),
            )
            await db.commit()
        return user

    async def check_rate_limit(self, user: User) -> bool:
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

        # Auto-reset if it's a new day
        if user.last_query_date != today:
            user.queries_today = 0
            user.last_query_date = today
            await self._update_usage(user)

        # Pro users have no limit
        if user.tier == "pro":
            return True

        return user.queries_today < user.queries_limit

    async def increment_usage(self, user: User) -> None:
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

        if user.last_query_date != today:
            user.queries_today = 0
            user.last_query_date = today

        user.queries_today += 1
        await self._update_usage(user)

    async def set_api_key(self, user_id: str, service: str, api_key: str) -> None:
        user = await self.get_user(user_id)
        if user is None:
            return
        user.api_keys[service] = api_key
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE users SET api_keys = ? WHERE id = ?",
                (json.dumps(user.api_keys), user_id),
            )
            await db.commit()

    async def get_api_keys(self, user_id: str) -> dict[str, str]:
        user = await self.get_user(user_id)
        if user is None:
            return {}
        return user.api_keys

    async def _update_usage(self, user: User) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE users SET queries_today = ?, last_query_date = ? WHERE id = ?",
                (user.queries_today, user.last_query_date, user.id),
            )
            await db.commit()

    @staticmethod
    def _row_to_user(row) -> User:
        return User(
            id=row[0],
            email=row[1],
            name=row[2],
            provider=row[3],
            created_at=datetime.fromisoformat(row[4]),
            api_keys=json.loads(row[5]),
            tier=row[6],
            queries_today=row[7],
            queries_limit=row[8],
            last_query_date=row[9],
        )
