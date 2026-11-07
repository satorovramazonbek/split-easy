"""Application settings read from environment variables.

Secrets must never be committed (DESIGN.md, section 13). Copy ``.env.example``
to ``.env`` or export the variables in the shell before starting the server.
"""

import logging
import os
import secrets
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = "sqlite:///./spliteasy.db"
DEFAULT_TOKEN_MINUTES = 60


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    access_token_minutes: int


def load_settings() -> Settings:
    secret_key = os.environ.get("SPLITEASY_SECRET_KEY")
    if not secret_key:
        # Development fallback: tokens become invalid after every restart.
        secret_key = secrets.token_urlsafe(32)
        logger.warning(
            "SPLITEASY_SECRET_KEY is not set; using a temporary random key. "
            "Issued tokens will stop working after a restart."
        )
    return Settings(
        database_url=os.environ.get("SPLITEASY_DATABASE_URL", DEFAULT_DATABASE_URL),
        secret_key=secret_key,
        access_token_minutes=int(
            os.environ.get("SPLITEASY_ACCESS_TOKEN_MINUTES", DEFAULT_TOKEN_MINUTES)
        ),
    )


settings = load_settings()
