"""Validated bootstrap settings and persistent configuration boundaries."""

import os
from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.engine import URL


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
        values = {
            key: os.environ[f"OPTIKEEP_{key.upper()}"]
            for key in cls.model_fields
            if f"OPTIKEEP_{key.upper()}" in os.environ
        }
        backend = os.environ.get("OPTIKEEP_DATABASE_BACKEND", "").strip()
        if backend == "postgresql":
            fields = {}
            for name in ("host", "database", "username", "password"):
                key = f"OPTIKEEP_POSTGRES_{name.upper()}"
                if not os.environ.get(key):
                    raise ValueError(f"{key} is required for PostgreSQL")
                fields[name] = os.environ[key]
            try:
                port = int(os.environ.get("OPTIKEEP_POSTGRES_PORT", "5432"))
                if not 1 <= port <= 65535:
                    raise ValueError
            except ValueError:
                raise ValueError(
                    "OPTIKEEP_POSTGRES_PORT must be 1 through 65535"
                ) from None
            values["database_url"] = URL.create(
                "postgresql+psycopg", port=port, **fields
            ).render_as_string(hide_password=False)
        elif backend == "sqlite3":
            path = os.environ.get("OPTIKEEP_SQLITE_PATH", "/config/optikeep.sqlite3")
            if not Path(path).is_absolute():
                raise ValueError("OPTIKEEP_SQLITE_PATH must be an absolute path")
            values["database_url"] = URL.create(
                "sqlite", database=path
            ).render_as_string(hide_password=False)
        elif backend:
            raise ValueError("OPTIKEEP_DATABASE_BACKEND must be sqlite3 or postgresql")
        return cls(**values)

    def public(self) -> dict:
        """Return bootstrap settings with credentials and DSNs redacted."""
        data = self.model_dump(mode="json")
        data["api_token"] = data["daemon_token"] = "configured"
        data["database_url"] = self.database_url.split(":", 1)[0]
        return data
