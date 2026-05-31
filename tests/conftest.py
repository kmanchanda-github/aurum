"""
Shared pytest fixtures.

os.environ overrides run at module load time so they take effect
before any src.* module is first imported (and before module-level
singletons like `engine` and `settings` are created).
"""
import os

os.environ["USE_SQLITE"] = "true"
os.environ["USE_IN_MEMORY_CACHE"] = "true"
os.environ.setdefault("SECRET_KEY", "test-secret-key-change-me-in-production-32!")
os.environ.setdefault("LLM_PROVIDER", "anthropic")
os.environ.setdefault("LLM_MODEL", "claude-opus-4-7")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_aurum.db"

import uuid

import pytest


@pytest.fixture(scope="session")
def app():
    from src.api.main import app as fastapi_app
    return fastapi_app


@pytest.fixture(scope="session")
def client(app):
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


@pytest.fixture
def unique_email() -> str:
    return f"user_{uuid.uuid4().hex[:8]}@test.com"


@pytest.fixture
def registered_user(client, unique_email):
    """Register a fresh user and return (email, password, token)."""
    password = "TestPass123!"
    resp = client.post("/api/auth/register", json={"email": unique_email, "password": password})
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    return {"email": unique_email, "password": password, "token": token}


@pytest.fixture
def auth_headers(registered_user):
    return {"Authorization": f"Bearer {registered_user['token']}"}
