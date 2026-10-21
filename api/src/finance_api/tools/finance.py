"""Finance tools the model can call. A port of web/lib/tools/finance-tools.ts.

Each tool has:
- an input model (Pydantic), used both to validate the model's arguments and to generate
  the JSON Schema Gemini sees, like `inputSchema: z.object(...)` in the AI SDK;
- an async function that calls Alpha Vantage and returns an output model from
  schemas/finance.py.

TOOLS maps the tool names the frontend renders (`tool-getQuote`, ...) to those pieces.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from google.genai import types
from pydantic import BaseModel, Field

from finance_api.alpha_vantage import (
    AlphaVantageClient,
    parse_alpha_vantage_timestamp,
    to_iso_timestamp,
)
from finance_api.schemas.finance import (
    HistoricalPrice,
    HistoricalPrices,
    NewsItem,
    NewsResult,
    Quote,
)


class ToolError(Exception):
    """A tool couldn't produce a result. The message is shown to the model and the user."""


# --- Inputs ---------------------------------------------------------------------------


class QuoteInput(BaseModel):
    symbol: str = Field(description="Ticker, e.g. NVDA")


class NewsInput(BaseModel):
    symbol: str
    limit: int = Field(default=5, gt=0)


class HistoricalPricesInput(BaseModel):
    symbol: str
    days: int = Field(default=30, gt=0)


# --- Tools ----------------------------------------------------------------------------


async def get_quote(av: AlphaVantageClient, args: QuoteInput) -> Quote:
    data = await av.request({"function": "GLOBAL_QUOTE", "symbol": args.symbol})
    quote = data.get("Global Quote")
    if not isinstance(quote, dict) or not quote.get("05. price"):
        raise ToolError(f"No quote data found for {args.symbol}")

    trading_day = date.fromisoformat(quote["07. latest trading day"])
    return Quote(
        symbol=args.symbol,
        price=float(quote["05. price"]),
        change_percent=float(quote["10. change percent"].replace("%", "")),
        volume=int(quote["06. volume"]),
        as_of=to_iso_timestamp(
            datetime(trading_day.year, trading_day.month, trading_day.day, tzinfo=UTC)
        ),
    )


async def get_news(av: AlphaVantageClient, args: NewsInput) -> NewsResult:
    data = await av.request(
        {"function": "NEWS_SENTIMENT", "tickers": args.symbol, "limit": str(args.limit)}
    )
    feed = data.get("feed")
    if not isinstance(feed, list):
        return NewsResult(items=[])

    return NewsResult(
        items=[
            NewsItem(
                headline=item["title"],
                summary=item["summary"],
                url=item["url"],
                published_at=parse_alpha_vantage_timestamp(item["time_published"]),
            )
            for item in feed[: args.limit]
        ]
    )


async def get_historical_prices(
    av: AlphaVantageClient, args: HistoricalPricesInput
) -> HistoricalPrices:
    data = await av.request(
        {
            "function": "TIME_SERIES_DAILY",
            "symbol": args.symbol,
            # "compact" returns the latest 100 days; "full" returns 20+ years.
            "outputsize": "full" if args.days > 100 else "compact",
        }
    )
    series = data.get("Time Series (Daily)")
    if not isinstance(series, dict):
        raise ToolError(f"No historical data found for {args.symbol}")

    # Keys are "YYYY-MM-DD", so sorting the strings sorts by date (oldest first).
    latest_days = sorted(series.items())[-args.days :]
    return HistoricalPrices(
        candles=[
            HistoricalPrice(
                time=day,
                open=float(values["1. open"]),
                high=float(values["2. high"]),
                low=float(values["3. low"]),
                close=float(values["4. close"]),
                volume=int(values["5. volume"]),
            )
            for day, values in latest_days
        ]
    )


# --- Registry -------------------------------------------------------------------------


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    run: Callable[[AlphaVantageClient, Any], Awaitable[BaseModel]]

    def declaration(self) -> types.FunctionDeclaration:
        """What Gemini sees: the tool's name, description and argument JSON Schema."""
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters_json_schema=self.input_model.model_json_schema(),
        )


TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        Tool(
            name="getQuote",
            description="Get the latest price and daily change for a US equity ticker",
            input_model=QuoteInput,
            run=get_quote,
        ),
        Tool(
            name="getNews",
            description="Get recent news headlines for a US equity ticker",
            input_model=NewsInput,
            run=get_news,
        ),
        Tool(
            name="getHistoricalPrices",
            description="Get daily OHLCV candles for a US equity ticker over a date range",
            input_model=HistoricalPricesInput,
            run=get_historical_prices,
        ),
    )
}


async def run_tool(av: AlphaVantageClient, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Validate the model's arguments, run the tool, and return its JSON-ready output.

    Raises ToolError, AlphaVantageError or pydantic.ValidationError; the agent loop turns
    those into a tool error the model and the UI can see.
    """
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolError(f"Unknown tool: {name}")
    result = await tool.run(av, tool.input_model.model_validate(args))
    return result.model_dump()
