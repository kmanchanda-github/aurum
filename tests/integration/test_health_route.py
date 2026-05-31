"""Integration tests for /healthz endpoint."""
from __future__ import annotations

import pytest


def test_health_returns_200(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200


def test_health_response_has_required_fields(client):
    resp = client.get("/healthz")
    body = resp.json()
    assert "status" in body
    assert "db" in body
    assert "redis" in body
    assert "chroma" in body


def test_health_db_reports_ok(client):
    resp = client.get("/healthz")
    body = resp.json()
    # In test mode with SQLite the DB should be reachable
    assert body["db"] == "ok"


def test_health_status_is_ok_or_degraded(client):
    resp = client.get("/healthz")
    assert resp.json()["status"] in ("ok", "degraded")


def test_health_requires_no_auth(client):
    """Health endpoint must be open — no auth token needed."""
    resp = client.get("/healthz")
    assert resp.status_code != 401
    assert resp.status_code != 403
