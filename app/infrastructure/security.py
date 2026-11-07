"""Password hashing (Argon2) and JWT access tokens."""

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

ALGORITHM = "HS256"


class Argon2PasswordHasher:
    """Hashes passwords with Argon2id; plain passwords are never stored."""

    def __init__(self) -> None:
        self._hasher = PasswordHasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False


class JwtTokenService:
    """Issues and validates signed access tokens."""

    def __init__(self, secret_key: str, expires_minutes: int) -> None:
        self._secret_key = secret_key
        self._expires = timedelta(minutes=expires_minutes)

    def create_access_token(self, user_id: int) -> str:
        now = datetime.now(UTC)
        payload = {"sub": str(user_id), "iat": now, "exp": now + self._expires}
        return jwt.encode(payload, self._secret_key, algorithm=ALGORITHM)

    def decode_user_id(self, token: str) -> int | None:
        """Return the user id, or ``None`` if the token is invalid or expired."""
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[ALGORITHM],
                options={"require": ["sub", "exp"]},
            )
            return int(payload["sub"])
        except (jwt.PyJWTError, ValueError):
            return None
