"""Application configuration for the @nifty_ml backend."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    database_path: str = Field(
        default=os.path.join("data", "market_data.db"),
        description="Path to SQLite price database created by fetch_price_history.py",
    )
    allowed_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost", "http://localhost:5173", "http://localhost:3000"],
        description="CORS origins permitted to access the API",
    )
    app_name: str = Field(default="nifty-ml-backend")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


