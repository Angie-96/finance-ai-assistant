import pytest
from pydantic import ValidationError

from finance_api.schemas.finance import NewsItem, Quote


def test_quote_serializes_to_camel_case() -> None:
    quote = Quote(symbol="NVDA", price=1.5, change_percent=-2.0, volume=10, as_of="x")

    assert quote.model_dump() == {
        "symbol": "NVDA",
        "price": 1.5,
        "changePercent": -2.0,
        "volume": 10,
        "asOf": "x",
    }


def test_news_url_is_kept_exactly_as_given() -> None:
    item = NewsItem(headline="h", summary="s", url="https://example.com", published_at="t")

    assert item.url == "https://example.com"  # not normalized to "https://example.com/"


@pytest.mark.parametrize("url", ["not a url", "javascript:alert(1)", "ftp://example.com/file"])
def test_news_url_must_be_http(url: str) -> None:
    with pytest.raises(ValidationError):
        NewsItem(headline="h", summary="s", url=url, published_at="t")
