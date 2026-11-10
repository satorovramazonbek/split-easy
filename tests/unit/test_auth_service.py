from datetime import UTC, datetime

import pytest

from app.domain.models import User
from app.repositories.interfaces.user_repository import DuplicateUserError
from app.services.auth_service import (
    AuthService,
    InvalidCredentialsError,
    UserAlreadyExistsError,
)
from tests.unit.fakes import InMemoryUserRepository

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


class FakeHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{password}"


class FakeTokens:
    def create_access_token(self, user_id: int) -> str:
        return f"token-{user_id}"

    def decode_user_id(self, token: str) -> int | None:
        prefix = "token-"
        return int(token[len(prefix) :]) if token.startswith(prefix) else None


@pytest.fixture
def repo() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@pytest.fixture
def service(repo: InMemoryUserRepository) -> AuthService:
    return AuthService(repo, FakeHasher(), FakeTokens(), clock=lambda: NOW)


def test_register_stores_hash_not_plain_password(service: AuthService) -> None:
    user = service.register("aziza", "aziza@example.com", "secret123")

    assert user.id == 1
    assert user.password_hash == "hashed:secret123"
    assert user.created_at == NOW


def test_register_normalizes_username_and_email(service: AuthService) -> None:
    user = service.register("  Aziza ", " Aziza@Example.COM ", "secret123")

    assert user.username == "aziza"
    assert user.email == "aziza@example.com"


def test_register_rejects_taken_username(service: AuthService) -> None:
    service.register("aziza", "a@example.com", "secret123")

    with pytest.raises(UserAlreadyExistsError):
        service.register("AZIZA", "other@example.com", "secret123")


def test_register_rejects_taken_email(service: AuthService) -> None:
    service.register("aziza", "a@example.com", "secret123")

    with pytest.raises(UserAlreadyExistsError):
        service.register("other", "A@example.com", "secret123")


def test_register_maps_storage_duplicate_error(repo, service: AuthService) -> None:
    def failing_add(user: User) -> User:
        raise DuplicateUserError("UNIQUE constraint failed")

    repo.add = failing_add

    with pytest.raises(UserAlreadyExistsError):
        service.register("aziza", "a@example.com", "secret123")


@pytest.mark.parametrize("login", ["aziza", "AZIZA", "aziza@example.com"])
def test_login_by_username_or_email(service: AuthService, login: str) -> None:
    user = service.register("aziza", "aziza@example.com", "secret123")

    assert service.login(login, "secret123") == f"token-{user.id}"


@pytest.mark.parametrize(
    ("login", "password"),
    [("aziza", "wrong-pass"), ("nobody", "secret123"), ("x@example.com", "secret123")],
)
def test_login_rejects_bad_credentials(
    service: AuthService, login: str, password: str
) -> None:
    service.register("aziza", "aziza@example.com", "secret123")

    with pytest.raises(InvalidCredentialsError):
        service.login(login, password)


def test_get_current_user_from_token(service: AuthService) -> None:
    user = service.register("aziza", "aziza@example.com", "secret123")
    token = service.login("aziza", "secret123")

    assert service.get_current_user(token) == user


@pytest.mark.parametrize("token", ["garbage", "token-999"])
def test_get_current_user_rejects_invalid_token(
    service: AuthService, token: str
) -> None:
    with pytest.raises(InvalidCredentialsError):
        service.get_current_user(token)


# --- Profile: change username (FR-4) -------------------------------------------


def test_change_username_saves_normalized_name(service: AuthService, repo) -> None:
    user = service.register("aziza", "aziza@example.com", "secret123")

    updated = service.change_username(user, "  Aziza_A ")

    assert updated.username == "aziza_a"
    assert repo.get_by_id(user.id).username == "aziza_a"
    assert updated.email == user.email


def test_change_username_lets_user_log_in_with_new_name(service: AuthService) -> None:
    user = service.register("aziza", "aziza@example.com", "secret123")

    service.change_username(user, "aziza_a")

    assert service.login("aziza_a", "secret123") == f"token-{user.id}"
    with pytest.raises(InvalidCredentialsError):
        service.login("aziza", "secret123")


def test_change_username_rejects_name_of_another_user(service: AuthService) -> None:
    user = service.register("aziza", "aziza@example.com", "secret123")
    service.register("ramazon", "ramazon@example.com", "secret123")

    with pytest.raises(UserAlreadyExistsError):
        service.change_username(user, "Ramazon")


def test_change_username_to_same_name_is_allowed(service: AuthService) -> None:
    user = service.register("aziza", "aziza@example.com", "secret123")

    assert service.change_username(user, "AZIZA").username == "aziza"


def test_change_username_lost_race_is_reported_as_taken(service: AuthService) -> None:
    user = service.register("aziza", "aziza@example.com", "secret123")

    class RacingRepo(InMemoryUserRepository):
        def update_username(self, user_id: int, username: str) -> User:
            raise DuplicateUserError(username)

    racing = AuthService(RacingRepo(), FakeHasher(), FakeTokens(), clock=lambda: NOW)

    with pytest.raises(UserAlreadyExistsError):
        racing.change_username(user, "ramazon")
