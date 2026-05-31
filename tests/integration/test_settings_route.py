"""Integration tests for /api/settings endpoints."""
from __future__ import annotations

import pytest


def test_get_user_settings_returns_200(client, session_auth_headers):
    resp = client.get("/api/settings", headers=session_auth_headers)
    assert resp.status_code == 200


def test_get_user_settings_unauthenticated(client):
    resp = client.get("/api/settings")
    assert resp.status_code in (401, 403)


def test_patch_user_settings_watchlist(client, session_auth_headers):
    resp = client.patch(
        "/api/settings",
        json={"watchlist": ["AAPL", "MSFT", "NVDA"]},
        headers=session_auth_headers,
    )
    assert resp.status_code in (200, 204)


def test_patch_user_settings_risk_tolerance(client, session_auth_headers):
    resp = client.patch(
        "/api/settings",
        json={"risk_tolerance": "aggressive"},
        headers=session_auth_headers,
    )
    assert resp.status_code in (200, 204)


def test_get_adapter_health_structure(client, session_auth_headers):
    resp = client.get("/api/settings/adapters/health", headers=session_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)


def test_get_adapter_health_authenticated(client, session_auth_headers):
    resp = client.get("/api/settings/adapters/health", headers=session_auth_headers)
    assert resp.status_code == 200
