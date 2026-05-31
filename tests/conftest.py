"""
Shared pytest fixtures.

os.environ overrides run at module load time so they take effect
before any src.* module is first imported (and before module-level
singletons like `engine` and `settings` are created).
"""
import os
from unittest.mock import patch

os.environ["USE_SQLITE"] = "true"
os.environ["USE_IN_MEMORY_CACHE"] = "true"
os.environ.setdefault("SECRET_KEY", "test-secret-key-change-me-in-production-32!")
os.environ.setdefault("LLM_PROVIDER", "anthropic")
os.environ.setdefault("LLM_MODEL", "claude-opus-4-7")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_aurum.db"

# Disable rate limiting for the test suite by monkey-patching the limiter
# module before the app is imported. The @limiter.limit decorator stores limit
# specs on the function; at request time slowapi calls limiter._check_request_limit.
# We replace the entire limiter instance with one that has a no-op limit decorator.

def _noop_decorator(*args, **kwargs):
    """Return an identity decorator regardless of limit spec."""
    def decorator(f):
        return f
    return decorator

# Patch BEFORE app is imported (conftest runs before fixtures)
from src.api import limiter as _limiter_mod  # import the module  # noqa: E402
_limiter_mod.limiter.limit = _noop_decorator  # make @limiter.limit a no-op going forward

# Also clear any already-applied slowapi wrappers on route functions by
# replacing the middleware-level storage check with a pass-through.
import slowapi.extension as _slowapi_ext  # noqa: E402

_orig_check = _slowapi_ext.Limiter._check_request_limit

async def _unlimited_check(self, request, response, endpoint, *args, **kwargs):
    # Set the state attribute slowapi reads after the check, then return
    try:
        request.state.view_rate_limit = ("unlimited", None)
    except Exception:
        pass

_slowapi_ext.Limiter._check_request_limit = _unlimited_check

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


# ── Session-scoped auth — reuse one account to avoid rate-limit 429s ──────────
# Tests that only need *a valid token* (not a fresh user) should use these.

@pytest.fixture(scope="session")
def session_auth_headers(client):
    """One registered user shared across the whole test session."""
    email = f"session_{uuid.uuid4().hex[:6]}@test.com"
    password = "SessionPass123!"
    resp = client.post("/api/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, f"Session user registration failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
