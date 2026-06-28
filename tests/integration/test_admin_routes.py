"""Integration tests for admin API routes."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest


def _make_admin(client, monkeypatch):
    """Register a user and make them an admin via settings."""
    email = f"admin_{uuid.uuid4().hex[:6]}@test.com"
    password = "AdminPass123!"
    resp = client.post("/api/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    # Patch admin_email_list to include this user
    monkeypatch.setattr(
        "src.api.deps.settings",
        type("S", (), {"admin_email_list": [email.lower()]})(),
    )
    return {"Authorization": f"Bearer {token}"}


def _make_non_admin(client):
    email = f"user_{uuid.uuid4().hex[:6]}@test.com"
    resp = client.post("/api/auth/register", json={"email": email, "password": "UserPass123!"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestAdminStats:
    def test_stats_returns_200(self, client, monkeypatch):
        headers = _make_admin(client, monkeypatch)
        resp = client.get("/api/admin/stats", headers=headers)
        assert resp.status_code == 200

    def test_stats_has_required_fields(self, client, monkeypatch):
        headers = _make_admin(client, monkeypatch)
        body = client.get("/api/admin/stats", headers=headers).json()
        assert "total_users" in body
        assert "total_conversations" in body
        assert "total_messages" in body
        assert "estimated_cost_usd" in body

    def test_stats_requires_admin(self, client, monkeypatch):
        headers = _make_non_admin(client)
        # Set admin_email_list to something else so this user isn't admin
        monkeypatch.setattr(
            "src.api.deps.settings",
            type("S", (), {"admin_email_list": ["someone_else@test.com"]})(),
        )
        resp = client.get("/api/admin/stats", headers=headers)
        assert resp.status_code == 403

    def test_stats_requires_auth(self, client):
        resp = client.get("/api/admin/stats")
        assert resp.status_code in (401, 403)


class TestAdminConversations:
    def test_list_conversations_returns_200(self, client, monkeypatch):
        headers = _make_admin(client, monkeypatch)
        resp = client.get("/api/admin/conversations", headers=headers)
        assert resp.status_code == 200

    def test_list_conversations_structure(self, client, monkeypatch):
        headers = _make_admin(client, monkeypatch)
        body = client.get("/api/admin/conversations", headers=headers).json()
        assert "items" in body
        assert "total" in body
        assert "page" in body
        assert "per_page" in body

    def test_list_conversations_pagination(self, client, monkeypatch):
        headers = _make_admin(client, monkeypatch)
        resp = client.get("/api/admin/conversations?page=1&per_page=5", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 1
        assert body["per_page"] == 5

    def test_conversation_trace_404_on_unknown(self, client, monkeypatch):
        headers = _make_admin(client, monkeypatch)
        resp = client.get("/api/admin/conversations/nonexistent-id/trace", headers=headers)
        assert resp.status_code == 404


class TestAdminUsers:
    def test_list_users_returns_200(self, client, monkeypatch):
        headers = _make_admin(client, monkeypatch)
        resp = client.get("/api/admin/users", headers=headers)
        assert resp.status_code == 200

    def test_list_users_structure(self, client, monkeypatch):
        headers = _make_admin(client, monkeypatch)
        body = client.get("/api/admin/users", headers=headers).json()
        assert "items" in body
        assert "total" in body
        assert body["total"] >= 1  # at least the admin we created

    def test_list_users_items_have_fields(self, client, monkeypatch):
        headers = _make_admin(client, monkeypatch)
        body = client.get("/api/admin/users", headers=headers).json()
        if body["items"]:
            item = body["items"][0]
            assert "id" in item
            assert "email" in item
            assert "conversation_count" in item
