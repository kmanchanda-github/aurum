"""Integration tests for the /api/goals endpoints."""
from __future__ import annotations

import pytest


def _goal_payload(**overrides) -> dict:
    base = {
        "name": "Retirement Fund",
        "goal_type": "retirement",
        "target_amount": "500000",
        "current_amount": "10000",
        "monthly_contribution": "1500",
        "risk_tolerance": "moderate",
        "priority": 1,
    }
    base.update(overrides)
    return base


def test_list_goals_returns_empty_for_new_user(client, auth_headers):
    resp = client.get("/api/goals", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_goal_returns_201(client, auth_headers):
    resp = client.post("/api/goals", json=_goal_payload(), headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Retirement Fund"
    assert body["goal_type"] == "retirement"
    assert "id" in body


def test_create_goal_appears_in_list(client, auth_headers):
    client.post("/api/goals", json=_goal_payload(name="Emergency Fund"), headers=auth_headers)
    resp = client.get("/api/goals", headers=auth_headers)
    assert resp.status_code == 200
    names = [g["name"] for g in resp.json()]
    assert "Emergency Fund" in names


def test_create_multiple_goals(client, auth_headers):
    client.post("/api/goals", json=_goal_payload(name="House Down Payment", priority=1), headers=auth_headers)
    client.post("/api/goals", json=_goal_payload(name="Car Fund", priority=2), headers=auth_headers)
    resp = client.get("/api/goals", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


def test_update_goal_changes_name(client, auth_headers):
    create_resp = client.post("/api/goals", json=_goal_payload(name="Old Name"), headers=auth_headers)
    goal_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/goals/{goal_id}",
        json={"name": "New Name"},
        headers=auth_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "New Name"


def test_update_goal_not_found_returns_404(client, auth_headers):
    resp = client.patch(
        "/api/goals/nonexistent-id-00000000",
        json={"name": "X"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_delete_goal_returns_204(client, auth_headers):
    create_resp = client.post("/api/goals", json=_goal_payload(name="To Delete"), headers=auth_headers)
    goal_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/goals/{goal_id}", headers=auth_headers)
    assert del_resp.status_code == 204


def test_delete_goal_removes_from_list(client, auth_headers):
    create_resp = client.post("/api/goals", json=_goal_payload(name="Temporary Goal"), headers=auth_headers)
    goal_id = create_resp.json()["id"]

    client.delete(f"/api/goals/{goal_id}", headers=auth_headers)

    list_resp = client.get("/api/goals", headers=auth_headers)
    ids = [g["id"] for g in list_resp.json()]
    assert goal_id not in ids


def test_goals_require_authentication(client):
    resp = client.get("/api/goals")
    assert resp.status_code in (401, 403)


def test_goals_are_isolated_per_user(client, unique_email):
    # Create user A with a goal
    reg_a = client.post("/api/auth/register", json={"email": unique_email, "password": "Pass123!"})
    token_a = reg_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    client.post("/api/goals", json=_goal_payload(name="User A Goal"), headers=headers_a)

    # Create user B and verify they see no goals
    import uuid
    email_b = f"userb_{uuid.uuid4().hex[:6]}@test.com"
    reg_b = client.post("/api/auth/register", json={"email": email_b, "password": "Pass123!"})
    token_b = reg_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    resp_b = client.get("/api/goals", headers=headers_b)
    assert resp_b.status_code == 200
    names = [g["name"] for g in resp_b.json()]
    assert "User A Goal" not in names
