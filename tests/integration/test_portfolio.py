"""Integration tests for portfolio CRUD endpoints."""
import pytest


HOLDING_PAYLOAD = {
    "symbol": "AAPL",
    "quantity": "10.5",
    "cost_basis": "1500.00",
    "asset_class": "stock",
}


@pytest.fixture
def portfolio_id(client, auth_headers):
    resp = client.post("/api/portfolio", json={"name": "My Portfolio"}, headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()["id"]


# ── Portfolio CRUD ────────────────────────────────────────────────────────────

def test_create_portfolio(client, auth_headers):
    resp = client.post("/api/portfolio", json={"name": "Growth Fund"}, headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Growth Fund"
    assert "id" in body


def test_list_portfolios(client, auth_headers, portfolio_id):
    resp = client.get("/api/portfolio", headers=auth_headers)
    assert resp.status_code == 200
    portfolios = resp.json()
    assert isinstance(portfolios, list)
    ids = [p["id"] for p in portfolios]
    assert portfolio_id in ids


def test_get_single_portfolio(client, auth_headers, portfolio_id):
    resp = client.get(f"/api/portfolio/{portfolio_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == portfolio_id


def test_get_other_users_portfolio_returns_404(client, unique_email, portfolio_id):
    # Create a second user
    resp = client.post("/api/auth/register", json={"email": unique_email, "password": "OtherPass1!"})
    other_token = resp.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # Second user cannot access first user's portfolio
    resp = client.get(f"/api/portfolio/{portfolio_id}", headers=other_headers)
    assert resp.status_code == 404


def test_delete_portfolio(client, auth_headers):
    create_resp = client.post("/api/portfolio", json={"name": "Temp Portfolio"}, headers=auth_headers)
    pid = create_resp.json()["id"]

    del_resp = client.delete(f"/api/portfolio/{pid}", headers=auth_headers)
    assert del_resp.status_code == 204

    get_resp = client.get(f"/api/portfolio/{pid}", headers=auth_headers)
    assert get_resp.status_code == 404


# ── Holdings CRUD ─────────────────────────────────────────────────────────────

def test_add_holding(client, auth_headers, portfolio_id):
    resp = client.post(
        f"/api/portfolio/{portfolio_id}/holdings",
        json=HOLDING_PAYLOAD,
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert "id" in body


def test_list_holdings(client, auth_headers, portfolio_id):
    client.post(f"/api/portfolio/{portfolio_id}/holdings", json=HOLDING_PAYLOAD, headers=auth_headers)
    resp = client.get(f"/api/portfolio/{portfolio_id}/holdings", headers=auth_headers)
    assert resp.status_code == 200
    holdings = resp.json()
    assert isinstance(holdings, list)
    assert any(h["symbol"] == "AAPL" for h in holdings)


def test_delete_holding(client, auth_headers, portfolio_id):
    add_resp = client.post(
        f"/api/portfolio/{portfolio_id}/holdings",
        json=HOLDING_PAYLOAD,
        headers=auth_headers,
    )
    hid = add_resp.json()["id"]

    del_resp = client.delete(
        f"/api/portfolio/{portfolio_id}/holdings/{hid}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204


def test_portfolio_requires_auth(client, portfolio_id):
    resp = client.get(f"/api/portfolio/{portfolio_id}")
    assert resp.status_code == 401
