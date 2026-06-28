"""Integration tests for /api/portfolio endpoints."""
from __future__ import annotations

import uuid
import pytest


def _portfolio_body(name: str = "My Portfolio") -> dict:
    return {"name": name}


def _holding_body(symbol: str = "AAPL", quantity: float = 10.0, cost_basis: float = 150.0) -> dict:
    return {"symbol": symbol, "quantity": quantity, "cost_basis": cost_basis}


# ── Portfolio CRUD ────────────────────────────────────────────────────────────


def test_create_portfolio_returns_201(client, session_auth_headers):
    name = f"Portfolio_{uuid.uuid4().hex[:6]}"
    resp = client.post("/api/portfolio", json=_portfolio_body(name), headers=session_auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == name
    assert "id" in body


def test_list_portfolios_returns_list(client, session_auth_headers):
    resp = client.get("/api/portfolio", headers=session_auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_create_portfolio_appears_in_list(client, session_auth_headers):
    name = f"Traceable_{uuid.uuid4().hex[:6]}"
    client.post("/api/portfolio", json=_portfolio_body(name), headers=session_auth_headers)
    resp = client.get("/api/portfolio", headers=session_auth_headers)
    names = [p["name"] for p in resp.json()]
    assert name in names


def test_get_portfolio_detail(client, session_auth_headers):
    name = f"Detail_{uuid.uuid4().hex[:6]}"
    pid = client.post("/api/portfolio", json=_portfolio_body(name),
                      headers=session_auth_headers).json()["id"]
    resp = client.get(f"/api/portfolio/{pid}", headers=session_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == name


def test_get_nonexistent_portfolio_returns_404(client, session_auth_headers):
    resp = client.get("/api/portfolio/nonexistent-id-000", headers=session_auth_headers)
    assert resp.status_code == 404


def test_portfolio_requires_auth(client):
    resp = client.get("/api/portfolio")
    assert resp.status_code in (401, 403)


def test_other_user_cannot_see_portfolio(client):
    """Portfolio created by user A is not visible to user B."""
    email_a = f"pf_a_{uuid.uuid4().hex[:6]}@test.com"
    reg_a = client.post("/api/auth/register", json={"email": email_a, "password": "Pass123!"})
    headers_a = {"Authorization": f"Bearer {reg_a.json()['access_token']}"}
    name = f"UserA_Portfolio_{uuid.uuid4().hex[:6]}"
    client.post("/api/portfolio", json=_portfolio_body(name), headers=headers_a)

    email_b = f"pf_b_{uuid.uuid4().hex[:6]}@test.com"
    reg_b = client.post("/api/auth/register", json={"email": email_b, "password": "Pass123!"})
    headers_b = {"Authorization": f"Bearer {reg_b.json()['access_token']}"}
    resp_b = client.get("/api/portfolio", headers=headers_b)
    assert all(p["name"] != name for p in resp_b.json())


# ── Holdings ──────────────────────────────────────────────────────────────────


def test_add_holding_to_portfolio(client, session_auth_headers):
    pid = client.post("/api/portfolio",
                      json=_portfolio_body(f"Hold_{uuid.uuid4().hex[:6]}"),
                      headers=session_auth_headers).json()["id"]
    resp = client.post(f"/api/portfolio/{pid}/holdings",
                       json=_holding_body(), headers=session_auth_headers)
    assert resp.status_code == 201
    assert resp.json()["symbol"] == "AAPL"


def test_list_holdings_in_portfolio(client, session_auth_headers):
    pid = client.post("/api/portfolio",
                      json=_portfolio_body(f"HoldList_{uuid.uuid4().hex[:6]}"),
                      headers=session_auth_headers).json()["id"]
    client.post(f"/api/portfolio/{pid}/holdings",
                json=_holding_body("VTI", 20.0, 210.0), headers=session_auth_headers)
    resp = client.get(f"/api/portfolio/{pid}", headers=session_auth_headers)
    assert resp.status_code == 200
    holdings = resp.json().get("holdings", [])
    assert any(h["symbol"] == "VTI" for h in holdings)


def test_delete_holding(client, session_auth_headers):
    pid = client.post("/api/portfolio",
                      json=_portfolio_body(f"DelHold_{uuid.uuid4().hex[:6]}"),
                      headers=session_auth_headers).json()["id"]
    holding = client.post(f"/api/portfolio/{pid}/holdings",
                          json=_holding_body("BND", 15.0, 75.0),
                          headers=session_auth_headers).json()
    hid = holding["id"]
    del_resp = client.delete(f"/api/portfolio/{pid}/holdings/{hid}",
                             headers=session_auth_headers)
    assert del_resp.status_code == 204


def test_delete_holding_makes_portfolio_empty(client, session_auth_headers):
    """Deleting the only holding leaves the portfolio with no holdings."""
    pid = client.post("/api/portfolio",
                      json=_portfolio_body(f"EmptyPortfolio_{uuid.uuid4().hex[:6]}"),
                      headers=session_auth_headers).json()["id"]
    holding = client.post(f"/api/portfolio/{pid}/holdings",
                          json=_holding_body("MSFT", 5.0, 300.0),
                          headers=session_auth_headers).json()
    hid = holding["id"]
    client.delete(f"/api/portfolio/{pid}/holdings/{hid}", headers=session_auth_headers)

    detail = client.get(f"/api/portfolio/{pid}", headers=session_auth_headers).json()
    symbols = [h["symbol"] for h in detail.get("holdings", [])]
    assert "MSFT" not in symbols


def test_delete_portfolio(client, session_auth_headers):
    pid = client.post("/api/portfolio",
                      json=_portfolio_body(f"ToDelete_{uuid.uuid4().hex[:6]}"),
                      headers=session_auth_headers).json()["id"]
    del_resp = client.delete(f"/api/portfolio/{pid}", headers=session_auth_headers)
    assert del_resp.status_code == 204
    # Verify it's gone
    get_resp = client.get(f"/api/portfolio/{pid}", headers=session_auth_headers)
    assert get_resp.status_code == 404


def test_delete_portfolio_nonexistent(client, session_auth_headers):
    resp = client.delete("/api/portfolio/nonexistent-id", headers=session_auth_headers)
    assert resp.status_code == 404


def test_list_holdings_endpoint(client, session_auth_headers):
    pid = client.post("/api/portfolio",
                      json=_portfolio_body(f"HoldList2_{uuid.uuid4().hex[:6]}"),
                      headers=session_auth_headers).json()["id"]
    client.post(f"/api/portfolio/{pid}/holdings",
                json=_holding_body("VOO", 5.0, 400.0), headers=session_auth_headers)
    resp = client.get(f"/api/portfolio/{pid}/holdings", headers=session_auth_headers)
    assert resp.status_code == 200
    symbols = [h["symbol"] for h in resp.json()]
    assert "VOO" in symbols


def test_list_holdings_nonexistent_portfolio(client, session_auth_headers):
    resp = client.get("/api/portfolio/nonexistent-id/holdings", headers=session_auth_headers)
    assert resp.status_code == 404


def test_update_holding(client, session_auth_headers):
    pid = client.post("/api/portfolio",
                      json=_portfolio_body(f"UpdateHold_{uuid.uuid4().hex[:6]}"),
                      headers=session_auth_headers).json()["id"]
    holding = client.post(f"/api/portfolio/{pid}/holdings",
                          json=_holding_body("GLD", 3.0, 180.0),
                          headers=session_auth_headers).json()
    hid = holding["id"]
    patch_resp = client.patch(f"/api/portfolio/{pid}/holdings/{hid}",
                              json={"quantity": 5.0},
                              headers=session_auth_headers)
    assert patch_resp.status_code == 200
    assert float(patch_resp.json()["quantity"]) == 5.0


def test_update_holding_nonexistent(client, session_auth_headers):
    pid = client.post("/api/portfolio",
                      json=_portfolio_body(f"UpdateMiss_{uuid.uuid4().hex[:6]}"),
                      headers=session_auth_headers).json()["id"]
    resp = client.patch(f"/api/portfolio/{pid}/holdings/nonexistent-id",
                        json={"quantity": 1.0},
                        headers=session_auth_headers)
    assert resp.status_code == 404


def test_add_holding_nonexistent_portfolio(client, session_auth_headers):
    resp = client.post("/api/portfolio/nonexistent-id/holdings",
                       json=_holding_body(), headers=session_auth_headers)
    assert resp.status_code == 404


def test_delete_holding_nonexistent(client, session_auth_headers):
    pid = client.post("/api/portfolio",
                      json=_portfolio_body(f"DelMiss_{uuid.uuid4().hex[:6]}"),
                      headers=session_auth_headers).json()["id"]
    resp = client.delete(f"/api/portfolio/{pid}/holdings/nonexistent-id",
                         headers=session_auth_headers)
    assert resp.status_code == 404
