"""Integration tests for /api/market endpoints."""
from __future__ import annotations

import pytest


# ── Quote ─────────────────────────────────────────────────────────────────────


def test_get_quote_returns_200(client, session_auth_headers):
    resp = client.get("/api/market/quote/AAPL", headers=session_auth_headers)
    assert resp.status_code == 200


def test_get_quote_has_required_fields(client, session_auth_headers):
    resp = client.get("/api/market/quote/AAPL", headers=session_auth_headers)
    body = resp.json()
    assert "symbol" in body
    assert "price" in body
    assert "change" in body
    assert "change_pct" in body


def test_get_quote_symbol_uppercased(client, session_auth_headers):
    """Lowercase symbol should work — API upcases it."""
    resp = client.get("/api/market/quote/aapl", headers=session_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["symbol"] == "AAPL"


def test_get_quote_unauthenticated_returns_401(client):
    resp = client.get("/api/market/quote/AAPL")
    assert resp.status_code in (401, 403)


# ── History ───────────────────────────────────────────────────────────────────


def test_get_history_returns_bars(client, session_auth_headers):
    resp = client.get("/api/market/history/AAPL?period=1mo&interval=1d",
                      headers=session_auth_headers)
    assert resp.status_code == 200
    bars = resp.json()
    assert isinstance(bars, list)
    if bars:
        assert "close" in bars[0]
        assert "open" in bars[0]


def test_get_history_invalid_period_returns_422(client, session_auth_headers):
    resp = client.get("/api/market/history/AAPL?period=invalid",
                      headers=session_auth_headers)
    assert resp.status_code == 422


def test_get_history_unauthenticated(client):
    resp = client.get("/api/market/history/AAPL")
    assert resp.status_code in (401, 403)


# ── Indices ───────────────────────────────────────────────────────────────────


def test_get_indices_returns_list(client, session_auth_headers):
    resp = client.get("/api/market/indices", headers=session_auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_indices_unauthenticated(client):
    resp = client.get("/api/market/indices")
    assert resp.status_code in (401, 403)


# ── Movers ────────────────────────────────────────────────────────────────────


def test_get_movers_gainers(client, session_auth_headers):
    resp = client.get("/api/market/movers?type=gainers", headers=session_auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_movers_losers(client, session_auth_headers):
    resp = client.get("/api/market/movers?type=losers", headers=session_auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_movers_active(client, session_auth_headers):
    resp = client.get("/api/market/movers?type=active", headers=session_auth_headers)
    assert resp.status_code == 200


def test_get_movers_invalid_type(client, session_auth_headers):
    resp = client.get("/api/market/movers?type=invalid", headers=session_auth_headers)
    assert resp.status_code == 422


# ── Search ────────────────────────────────────────────────────────────────────


def test_search_symbols_returns_list(client, session_auth_headers):
    resp = client.get("/api/market/search?q=AAPL", headers=session_auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_search_symbols_unauthenticated(client):
    resp = client.get("/api/market/search?q=AAPL")
    assert resp.status_code in (401, 403)
