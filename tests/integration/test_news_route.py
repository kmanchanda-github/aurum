"""Integration tests for /api/news route."""
from __future__ import annotations

import uuid


def _fresh_headers(client) -> dict:
    email = f"news_{uuid.uuid4().hex[:6]}@test.com"
    resp = client.post("/api/auth/register", json={"email": email, "password": "Pass123!"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_news_default_query(client, session_auth_headers):
    resp = client.get("/api/news", headers=session_auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_news_custom_query(client, session_auth_headers):
    resp = client.get("/api/news?query=bitcoin&limit=3", headers=session_auth_headers)
    assert resp.status_code == 200


def test_news_items_have_required_fields(client, session_auth_headers):
    resp = client.get("/api/news?limit=3", headers=session_auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    for item in items:
        assert "title" in item
        assert "url" in item
        assert "source" in item
        assert "published_at" in item


def test_news_limit_respected(client, session_auth_headers):
    resp = client.get("/api/news?limit=2", headers=session_auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) <= 2


def test_news_requires_auth(client):
    resp = client.get("/api/news")
    assert resp.status_code in (401, 403)
