"""Registration, login and token-based identification of users."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from app.domain.models import User
from app.repositories.interfaces.user_repository import (
    DuplicateUserError,
    UserRepository,
)


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class TokenService(Protocol):
    def create_access_token(self, user_id: int) -> str: ...

    def decode_user_id(self, token: str) -> int | None: ...


class AuthError(Exception):
    """Base class for authentication errors."""


class UserAlreadyExistsError(AuthError):
    """Username or email is already taken."""


class InvalidCredentialsError(AuthError):
    """Wrong login or password, or an invalid token."""


def normalize_username(username: str) -> str:
    return username.strip().lower()


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthService:
    def __init__(
        self,
        users: UserRepository,
        hasher: PasswordHasher,
        tokens: TokenService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._tokens = tokens
        self._clock = clock

    def register(self, username: str, email: str, password: str) -> User:
        username = normalize_username(username)
        email = normalize_email(email)
        if self._users.get_by_username(username):
            raise UserAlreadyExistsError("Bu foydalanuvchi nomi band")
        if self._users.get_by_email(email):
            raise UserAlreadyExistsError("Bu email bilan ro'yxatdan o'tilgan")
        user = User(
            id=None,
            username=username,
            email=email,
            password_hash=self._hasher.hash(password),
            created_at=self._clock(),
        )
        try:
            return self._users.add(user)
        except DuplicateUserError as error:
            # Lost a race with a concurrent registration.
            raise UserAlreadyExistsError(
                "Bu foydalanuvchi nomi yoki email band"
            ) from error

    def login(self, login: str, password: str) -> str:
        """Accept username or email; return an access token."""
        login = login.strip().lower()
        user = (
            self._users.get_by_email(login)
            if "@" in login
            else self._users.get_by_username(login)
        )
        if user is None or not self._hasher.verify(password, user.password_hash):
            # Same message for both cases so logins cannot be enumerated.
            raise InvalidCredentialsError("Login yoki parol noto'g'ri")
        return self._tokens.create_access_token(user.id)

    def change_username(self, user: User, username: str) -> User:
        """FR-4: the user edits their profile name (the username).

        The name is normalized like at registration, so login keeps working
        with any letter case. Keeping the current name is not an error.
        """
        username = normalize_username(username)
        if username == user.username:
            return user
        if self._users.get_by_username(username):
            raise UserAlreadyExistsError("Bu foydalanuvchi nomi band")
        try:
            return self._users.update_username(user.id, username)
        except DuplicateUserError as error:
            # Lost a race with a concurrent change or registration.
            raise UserAlreadyExistsError("Bu foydalanuvchi nomi band") from error

    def get_current_user(self, token: str) -> User:
        user_id = self._tokens.decode_user_id(token)
        user = self._users.get_by_id(user_id) if user_id is not None else None
        if user is None:
            raise InvalidCredentialsError("Token yaroqsiz yoki muddati tugagan")
        return user
