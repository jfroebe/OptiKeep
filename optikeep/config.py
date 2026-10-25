"""Validated bootstrap settings and persistent configuration boundaries."""

import os
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class Settings(BaseModel):
    """Bound resource use and constrain all media access to configured roots."""

    database_url: str = "sqlite:////config/optikeep.sqlite3"
    media_root: Path = Path("/media")
    state_root: Path = Path("/config")
    api_token: str = Field(min_length=24)
    daemon_token: str = Field(min_length=24)
    batch_size: int = Field(default=128, ge=1, le=512)
    lease_seconds: int = Field(default=90, ge=30, le=3600)
    image_pixel_limit: int = Field(default=40_000_000, ge=1, le=200_000_000)
    process_timeout: int = Field(default=300, ge=1, le=3600)

    @field_validator("database_url")
    @classmethod
    def validate_backend(cls, value: str) -> str:
        """Reject implicit backend substitution and unsupported databases."""
        if not value.startswith(("sqlite:///", "postgresql+psycopg://")):
            raise ValueError("Choose sqlite:/// or postgresql+psycopg://")
        return value

    @classmethod
    def from_env(cls) -> "Settings":
        """Load explicit environment overrides without logging secrets."""
        return cls(
            **{
                key: os.environ[f"OPTIKEEP_{key.upper()}"]
                for key in cls.model_fields
                if f"OPTIKEEP_{key.upper()}" in os.environ
            }
        )

    def public(self) -> dict:
        """Return bootstrap settings with credentials and DSNs redacted."""
        data = self.model_dump(mode="json")
        data["api_token"] = data["daemon_token"] = "configured"
        data["database_url"] = self.database_url.split(":", 1)[0]
        return data
