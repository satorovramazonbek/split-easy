"""Application settings read from environment variables.

Secrets must never be committed (DESIGN.md, section 13). Copy ``.env.example``
to ``.env`` or export the variables in the shell before starting the server.
"""

import logging
import os
import secrets
from collections.abc import MutableMapping
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = "sqlite:///./spliteasy.db"
DEFAULT_TOKEN_MINUTES = 60
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    access_token_minutes: int
    # Send the login cookie only over HTTPS. Off by default for local http.
    cookie_secure: bool = False


def load_env_file(
    path: Path = ENV_FILE, environ: MutableMapping[str, str] = os.environ
) -> None:
    """Copy ``KEY=value`` lines from ``path`` into ``environ``.

    Variables already set in the shell win over the file. Blank lines and
    ``#`` comments are skipped; quotes around a value are removed. A missing
    file is not an error (the defaults below are used).
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        environ.setdefault(key, value)


def load_settings() -> Settings:
    load_env_file()
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
        cookie_secure=os.environ.get("SPLITEASY_COOKIE_SECURE", "0").lower()
        in {"1", "true", "yes"},
    )


settings = load_settings()
