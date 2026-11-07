"""User entity.

Pure Python: the domain layer knows nothing about the database or the web.
The password is stored only as a hash produced by the infrastructure layer.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class User:
    """A registered application user."""

    id: int | None
    username: str
    email: str
    password_hash: str
    created_at: datetime
