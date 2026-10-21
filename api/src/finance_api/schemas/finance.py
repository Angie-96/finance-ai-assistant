"""Tool output shapes. The Python equivalent of web/lib/schemas/finance.ts (Zod).

Fields are snake_case in Python but serialize to camelCase (`change_percent` ->
`changePercent`), so the JSON the frontend receives is identical to what the TypeScript
tools returned.
"""

from typing import Annotated

from pydantic import AfterValidator, HttpUrl, TypeAdapter

from finance_api.schemas.base import CamelModel

_http_url = TypeAdapter(HttpUrl)


def _check_http_url(value: str) -> str:
    # Validate like z.string().url(), but return the original string: HttpUrl would
    # normalize it (e.g. add a trailing slash). Only http(s) is allowed, which also keeps
    # `javascript:` links out of the news cards' <a href>.
    _http_url.validate_python(value)
    return value


Url = Annotated[str, AfterValidator(_check_http_url)]


class Quote(CamelModel):
    symbol: str
    price: float
    change_percent: float
    volume: int
    as_of: str  # ISO 8601, e.g. "2026-09-23T00:00:00.000Z"


class NewsItem(CamelModel):
    headline: str
    summary: str
    url: Url
    published_at: str  # ISO 8601


class NewsResult(CamelModel):
    items: list[NewsItem]


class HistoricalPrice(CamelModel):
    time: str  # "2026-09-21"
    open: float
    high: float
    low: float
    close: float
    volume: int


class HistoricalPrices(CamelModel):
    candles: list[HistoricalPrice]
