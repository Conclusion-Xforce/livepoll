"""Unit tests for app/auth.py."""

from app.auth import (
    create_admin_token,
    hash_password,
    verify_admin_token,
    verify_password,
)


def test_hash_password_returns_bcrypt_hash():
    hashed = hash_password("mypassword")
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert hashed != "mypassword"


def test_hash_password_is_non_deterministic():
    h1 = hash_password("mypassword")
    h2 = hash_password("mypassword")
    assert h1 != h2  # different salts


def test_verify_password_correct():
    hashed = hash_password("correct")
    assert verify_password("correct", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("correct")
    assert verify_password("wrong", hashed) is False


def test_admin_token_roundtrip():
    session_id = "abc-123"
    token = create_admin_token(session_id)
    assert isinstance(token, str)
    assert verify_admin_token(token) == session_id


def test_verify_admin_token_tampered_returns_none():
    token = create_admin_token("abc-123")
    tampered = token[:-4] + "XXXX"
    assert verify_admin_token(tampered) is None


def test_verify_admin_token_garbage_returns_none():
    assert verify_admin_token("not-a-valid-token") is None


def test_verify_admin_token_empty_returns_none():
    assert verify_admin_token("") is None
