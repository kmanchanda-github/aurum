"""Unit tests for JWT and password helpers."""
import pytest
from src.core.security import create_access_token, decode_token, hash_password, verify_password


def test_hash_and_verify_password():
    hashed = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", hashed)
    assert not verify_password("wrong-password", hashed)


def test_hash_produces_different_salts():
    h1 = hash_password("same-password")
    h2 = hash_password("same-password")
    assert h1 != h2  # bcrypt includes random salt


def test_create_and_decode_token():
    token = create_access_token(subject="user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert "exp" in payload


def test_decode_invalid_token_raises():
    with pytest.raises(ValueError, match="Invalid or expired token"):
        decode_token("not.a.valid.token")


def test_decode_tampered_token_raises():
    token = create_access_token(subject="user-abc")
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(ValueError):
        decode_token(tampered)
