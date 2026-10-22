"""Tool tests against saved Alpha Vantage responses (tests/fixtures/*.json).

The Alpha Vantage client is replaced by a fake that returns a fixture, so these tests
check only the tools' parsing; the client has its own tests.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from finance_api.tools.finance import TOOLS, ToolError, run_tool
from tests.fakes import FakeAlphaVantage

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / name).read_text())
    return data


# --- getQuote -------------------------------------------------------------------------


async def test_get_quote_parses_global_quote() -> None:
    av = FakeAlphaVantage({"GLOBAL_QUOTE": load_fixture("global_quote.json")})

    output = await run_tool(av, "getQuote", {"symbol": "NVDA"})

    assert av.calls == [{"function": "GLOBAL_QUOTE", "symbol": "NVDA"}]
    assert output == {
        "symbol": "NVDA",
        "price": 178.43,
        "changePercent": 1.6637,
        "volume": 151234567,
        "asOf": "2026-09-23T00:00:00.000Z",
    }


async def test_get_quote_without_data_raises() -> None:
    av = FakeAlphaVantage({"GLOBAL_QUOTE": {"Global Quote": {}}})

    with pytest.raises(ToolError, match="No quote data found for ZZZZ"):
        await run_tool(av, "getQuote", {"symbol": "ZZZZ"})


# --- getNews --------------------------------------------------------------------------


async def test_get_news_parses_feed_and_applies_limit() -> None:
    av = FakeAlphaVantage({"NEWS_SENTIMENT": load_fixture("news_sentiment.json")})

    output = await run_tool(av, "getNews", {"symbol": "AAPL", "limit": 2})

    assert av.calls == [{"function": "NEWS_SENTIMENT", "tickers": "AAPL", "limit": "2"}]
    assert output == {
        "items": [
            {
                "headline": "Apple unveils new chips",
                "summary": "Apple announced its next generation of in-house silicon.",
                "url": "https://example.com/apple-chips",
                "publishedAt": "2026-09-23T14:30:05.000Z",
            },
            {
                "headline": "Analysts raise Apple targets",
                "summary": "Several analysts raised their price targets after the event.",
                "url": "https://example.com/apple-targets",
                "publishedAt": "2026-09-22T09:00:00.000Z",
            },
        ]
    }


async def test_get_news_defaults_to_five_items() -> None:
    av = FakeAlphaVantage({"NEWS_SENTIMENT": load_fixture("news_sentiment.json")})

    await run_tool(av, "getNews", {"symbol": "AAPL"})

    assert av.calls[0]["limit"] == "5"


async def test_get_news_without_feed_returns_no_items() -> None:
    av = FakeAlphaVantage({})

    assert await run_tool(av, "getNews", {"symbol": "AAPL"}) == {"items": []}


# --- getHistoricalPrices --------------------------------------------------------------


async def test_get_historical_prices_returns_oldest_first() -> None:
    av = FakeAlphaVantage({"TIME_SERIES_DAILY": load_fixture("time_series_daily.json")})

    output = await run_tool(av, "getHistoricalPrices", {"symbol": "TSLA"})

    assert av.calls == [
        {"function": "TIME_SERIES_DAILY", "symbol": "TSLA", "outputsize": "compact"}
    ]
    assert [candle["time"] for candle in output["candles"]] == [
        "2026-09-21",
        "2026-09-22",
        "2026-09-23",
    ]
    assert output["candles"][-1] == {
        "time": "2026-09-23",
        "open": 250.0,
        "high": 255.5,
        "low": 248.1,
        "close": 254.2,
        "volume": 90000000,
    }


async def test_get_historical_prices_keeps_only_the_latest_days() -> None:
    av = FakeAlphaVantage({"TIME_SERIES_DAILY": load_fixture("time_series_daily.json")})

    output = await run_tool(av, "getHistoricalPrices", {"symbol": "TSLA", "days": 2})

    assert [candle["time"] for candle in output["candles"]] == ["2026-09-22", "2026-09-23"]


@pytest.mark.parametrize(("days", "outputsize"), [(100, "compact"), (101, "full")])
async def test_get_historical_prices_requests_full_history_beyond_100_days(
    days: int, outputsize: str
) -> None:
    av = FakeAlphaVantage({"TIME_SERIES_DAILY": load_fixture("time_series_daily.json")})

    await run_tool(av, "getHistoricalPrices", {"symbol": "TSLA", "days": days})

    assert av.calls[0]["outputsize"] == outputsize


async def test_get_historical_prices_without_data_raises() -> None:
    av = FakeAlphaVantage({})

    with pytest.raises(ToolError, match="No historical data found for TSLA"):
        await run_tool(av, "getHistoricalPrices", {"symbol": "TSLA"})


# --- Registry -------------------------------------------------------------------------


async def test_invalid_arguments_are_rejected_before_calling_alpha_vantage() -> None:
    av = FakeAlphaVantage({})

    with pytest.raises(ValidationError):
        await run_tool(av, "getHistoricalPrices", {"symbol": "TSLA", "days": 0})
    assert av.calls == []


async def test_unknown_tool_raises() -> None:
    with pytest.raises(ToolError, match="Unknown tool: getWeather"):
        await run_tool(FakeAlphaVantage({}), "getWeather", {})


def test_tool_names_match_what_the_frontend_renders() -> None:
    # Chat.tsx switches on "tool-getQuote", "tool-getNews" and "tool-getHistoricalPrices".
    assert set(TOOLS) == {"getQuote", "getNews", "getHistoricalPrices"}


def test_declarations_expose_argument_schemas_to_gemini() -> None:
    declaration = TOOLS["getHistoricalPrices"].declaration()

    assert declaration.name == "getHistoricalPrices"
    schema = declaration.parameters_json_schema
    assert isinstance(schema, dict)
    assert schema["required"] == ["symbol"]
    assert schema["properties"]["days"]["default"] == 30
