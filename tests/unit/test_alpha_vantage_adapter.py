"""Unit tests for AlphaVantageAdapter."""
from __future__ import annotations

from datetime import timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def patch_settings():
    """Inject a fake API key so the adapter can be constructed."""
    from pydantic import SecretStr

    mock_settings = MagicMock()
    mock_settings.alpha_vantage_api_key = SecretStr("fake-key-abc123")
    with patch("src.adapters.market.alpha_vantage_adapter.settings", mock_settings):
        yield mock_settings


def _make_adapter():
    from src.adapters.market.alpha_vantage_adapter import AlphaVantageAdapter
    return AlphaVantageAdapter()


def _mock_response(json_data: dict, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


@pytest.mark.asyncio
async def test_get_quote_returns_quote():
    adapter = _make_adapter()
    payload = {
        "Global Quote": {
            "05. price": "185.50",
            "09. change": "1.25",
            "10. change percent": "0.68%",
            "06. volume": "55000000",
        }
    }
    mock_resp = _mock_response(payload)
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("src.adapters.market.alpha_vantage_adapter.httpx.AsyncClient", return_value=mock_client):
        quote = await adapter.get_quote("AAPL")

    assert quote.symbol == "AAPL"
    assert quote.price == pytest.approx(185.50)
    assert quote.change == pytest.approx(1.25)
    assert quote.change_pct == pytest.approx(0.68)
    assert quote.volume == 55_000_000
    assert quote.source == "alpha_vantage"
    assert quote.as_of.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_get_quote_missing_fields_defaults_to_zero():
    adapter = _make_adapter()
    mock_resp = _mock_response({"Global Quote": {}})
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("src.adapters.market.alpha_vantage_adapter.httpx.AsyncClient", return_value=mock_client):
        quote = await adapter.get_quote("UNKNOWN")

    assert quote.price == 0.0
    assert quote.change == 0.0
    assert quote.volume == 0


@pytest.mark.asyncio
async def test_get_history_daily():
    adapter = _make_adapter()
    series = {
        "2024-01-02": {"1. open": "182.0", "2. high": "186.0", "3. low": "181.0", "4. close": "185.0", "5. volume": "100000"},
        "2024-01-03": {"1. open": "185.0", "2. high": "188.0", "3. low": "184.0", "4. close": "187.0", "5. volume": "120000"},
    }
    payload = {"Time Series (Daily)": series}
    mock_resp = _mock_response(payload)
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("src.adapters.market.alpha_vantage_adapter.httpx.AsyncClient", return_value=mock_client):
        bars = await adapter.get_history("AAPL", period="1mo", interval="1d")

    assert len(bars) == 2
    assert bars[0].close == pytest.approx(185.0)
    assert bars[1].close == pytest.approx(187.0)
    assert bars[0].ts.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_get_history_weekly():
    adapter = _make_adapter()
    payload = {"Weekly Time Series": {}}
    mock_resp = _mock_response(payload)
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("src.adapters.market.alpha_vantage_adapter.httpx.AsyncClient", return_value=mock_client):
        bars = await adapter.get_history("AAPL", period="6mo", interval="1wk")

    assert bars == []


def test_constructor_raises_without_api_key():
    from pydantic import SecretStr
    mock_settings = MagicMock()
    mock_settings.alpha_vantage_api_key = None
    with patch("src.adapters.market.alpha_vantage_adapter.settings", mock_settings):
        from src.adapters.market.alpha_vantage_adapter import AlphaVantageAdapter
        with pytest.raises(ValueError, match="ALPHA_VANTAGE_API_KEY"):
            AlphaVantageAdapter()


def test_adapter_metadata():
    adapter = _make_adapter()
    assert "quote" in adapter.capabilities
    assert "history" in adapter.capabilities
    assert adapter.name == "alpha_vantage"
