"""
Service configuration via environment variables.

All settings prefixed with KINSHIP_. Supabase creds are optional —
without them, the service runs in anonymous mode (no OAuth, just
free-tier metering via local SQLite).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_key: str = ""
    free_tier_limit: int = 50
    cors_origins: str = "*"
    db_path: str = ""
    graph_db_path: str = ""
    auth_enabled: bool = False

    model_config = {"env_prefix": "KINSHIP_"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)


settings = Settings()
