from datetime import UTC, datetime, timedelta

import jwt

from app.infrastructure.security import ALGORITHM, Argon2PasswordHasher, JwtTokenService

SECRET = "test-secret-key-that-is-long-enough-for-hs256"


def test_password_hash_roundtrip() -> None:
    hasher = Argon2PasswordHasher()

    password_hash = hasher.hash("secret123")

    assert password_hash != "secret123"
    assert password_hash.startswith("$argon2")
    assert hasher.verify("secret123", password_hash)
    assert not hasher.verify("wrong", password_hash)


def test_verify_returns_false_for_malformed_hash() -> None:
    assert not Argon2PasswordHasher().verify("secret123", "not-a-hash")


def test_token_roundtrip() -> None:
    tokens = JwtTokenService(SECRET, expires_minutes=5)

    assert tokens.decode_user_id(tokens.create_access_token(42)) == 42


def test_token_signed_with_other_key_is_rejected() -> None:
    token = JwtTokenService(SECRET + "x", 5).create_access_token(42)

    assert JwtTokenService(SECRET, 5).decode_user_id(token) is None


def test_expired_token_is_rejected() -> None:
    tokens = JwtTokenService(SECRET, expires_minutes=-1)

    assert tokens.decode_user_id(tokens.create_access_token(42)) is None


def test_token_without_expiry_is_rejected() -> None:
    token = jwt.encode({"sub": "42"}, SECRET, algorithm=ALGORITHM)

    assert JwtTokenService(SECRET, 5).decode_user_id(token) is None


def test_token_with_non_numeric_subject_is_rejected() -> None:
    exp = datetime.now(UTC) + timedelta(minutes=5)
    token = jwt.encode({"sub": "abc", "exp": exp}, SECRET, algorithm=ALGORITHM)

    assert JwtTokenService(SECRET, 5).decode_user_id(token) is None


def test_garbage_token_is_rejected() -> None:
    assert JwtTokenService(SECRET, 5).decode_user_id("not.a.token") is None
