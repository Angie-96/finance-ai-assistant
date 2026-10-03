"""Alpha Vantage client tests. HTTP is mocked with respx and Redis is in-memory
(fakeredis), so nothing here touches the network."""

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from itertools import pairwise

import httpx
import pytest
import respx
from fakeredis import FakeAsyncRedis

from finance_api.alpha_vantage import (
    BASE_URL,
    THROTTLE_KEY,
    AlphaVantageClient,
    AlphaVantageError,
    parse_alpha_vantage_timestamp,
    to_iso_timestamp,
)

QUOTE_PARAMS = {"function": "GLOBAL_QUOTE", "symbol": "NVDA"}
OK_BODY = {"Global Quote": {"05. price": "100.0"}}


@pytest.fixture
async def redis() -> AsyncIterator[FakeAsyncRedis]:
    redis = FakeAsyncRedis(decode_responses=True)
    yield redis
    await redis.aclose()


@pytest.fixture
async def client(redis: FakeAsyncRedis) -> AsyncIterator[AlphaVantageClient]:
    async with httpx.AsyncClient() as http:
        # A short interval keeps the throttle tests fast; the logic is the same at 1500.
        yield AlphaVantageClient(http, redis, "secret-key", min_interval_ms=200)


async def test_returns_json_and_sends_api_key(
    client: AlphaVantageClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(BASE_URL).respond(json=OK_BODY)

    data = await client.request(QUOTE_PARAMS)

    assert data == OK_BODY
    sent = route.calls.last.request.url.params
    assert sent["function"] == "GLOBAL_QUOTE"
    assert sent["symbol"] == "NVDA"
    assert sent["apikey"] == "secret-key"


async def test_second_identical_request_is_served_from_cache(
    client: AlphaVantageClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(BASE_URL).respond(json=OK_BODY)

    first = await client.request(QUOTE_PARAMS)
    second = await client.request(dict(reversed(QUOTE_PARAMS.items())))  # order doesn't matter

    assert first == second
    assert route.call_count == 1


async def test_cache_entries_expire_after_ttl(
    client: AlphaVantageClient, redis: FakeAsyncRedis, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(BASE_URL).respond(json=OK_BODY)

    await client.request(QUOTE_PARAMS)

    [key] = [k async for k in redis.scan_iter("av:cache:*")]
    assert 0 < await redis.ttl(key) <= 300


async def test_cache_keys_and_values_never_contain_the_api_key(
    client: AlphaVantageClient, redis: FakeAsyncRedis, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(BASE_URL).respond(json=OK_BODY)

    await client.request(QUOTE_PARAMS)

    async for key in redis.scan_iter("av:cache:*"):
        assert "secret-key" not in key
        value = await redis.get(key)
        assert value is not None
        assert "secret-key" not in str(value)


@pytest.mark.parametrize("error_key", ["Error Message", "Note", "Information"])
async def test_error_payloads_raise_and_are_not_cached(
    client: AlphaVantageClient, redis: FakeAsyncRedis, respx_mock: respx.MockRouter, error_key: str
) -> None:
    respx_mock.get(BASE_URL).respond(json={error_key: "Rate limit reached"})

    with pytest.raises(AlphaVantageError, match="Rate limit reached"):
        await client.request(QUOTE_PARAMS)

    assert [k async for k in redis.scan_iter("av:cache:*")] == []


async def test_http_error_status_raises(
    client: AlphaVantageClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(BASE_URL).respond(status_code=503)

    with pytest.raises(AlphaVantageError, match="status 503"):
        await client.request(QUOTE_PARAMS)


async def test_network_error_message_does_not_leak_the_url(
    client: AlphaVantageClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(BASE_URL).mock(side_effect=httpx.ConnectError("boom"))

    with pytest.raises(AlphaVantageError) as error:
        await client.request(QUOTE_PARAMS)

    assert "secret-key" not in str(error.value)
    assert "ConnectError" in str(error.value)


async def test_concurrent_requests_are_spaced_by_the_throttle(
    client: AlphaVantageClient, respx_mock: respx.MockRouter
) -> None:
    sent_at: list[float] = []

    def record(request: httpx.Request) -> httpx.Response:
        sent_at.append(time.monotonic())
        return httpx.Response(200, json=OK_BODY)

    respx_mock.get(BASE_URL).mock(side_effect=record)

    # Three different symbols fired at once, like a model calling several tools.
    await asyncio.gather(
        *(client.request({"function": "GLOBAL_QUOTE", "symbol": s}) for s in ("A", "B", "C"))
    )

    gaps = [later - earlier for earlier, later in pairwise(sent_at)]
    assert len(sent_at) == 3
    assert all(gap >= 0.19 for gap in gaps), gaps  # 200 ms interval, small timer slack


async def test_two_clients_share_the_throttle_through_redis(
    redis: FakeAsyncRedis, respx_mock: respx.MockRouter
) -> None:
    """Two clients stand in for two API instances talking to the same Redis."""
    sent_at: list[float] = []

    def record(request: httpx.Request) -> httpx.Response:
        sent_at.append(time.monotonic())
        return httpx.Response(200, json=OK_BODY)

    respx_mock.get(BASE_URL).mock(side_effect=record)

    async with httpx.AsyncClient() as http_a, httpx.AsyncClient() as http_b:
        instance_a = AlphaVantageClient(http_a, redis, "k", min_interval_ms=200)
        instance_b = AlphaVantageClient(http_b, redis, "k", min_interval_ms=200)
        await asyncio.gather(
            instance_a.request({"function": "GLOBAL_QUOTE", "symbol": "A"}),
            instance_b.request({"function": "GLOBAL_QUOTE", "symbol": "B"}),
        )

    assert len(sent_at) == 2
    assert abs(sent_at[1] - sent_at[0]) >= 0.19


async def test_gives_up_when_no_slot_frees_up_in_time(
    redis: FakeAsyncRedis, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(BASE_URL).respond(json=OK_BODY)
    await redis.set(THROTTLE_KEY, "1", px=10_000)  # someone else holds the slot

    async with httpx.AsyncClient() as http:
        client = AlphaVantageClient(http, redis, "k", throttle_timeout_seconds=0.1)
        with pytest.raises(AlphaVantageError, match="busy"):
            await client.request(QUOTE_PARAMS)

    assert route.call_count == 0


def test_parse_alpha_vantage_timestamp() -> None:
    assert parse_alpha_vantage_timestamp("20260923T143005") == "2026-09-23T14:30:05.000Z"


def test_parse_alpha_vantage_timestamp_rejects_other_formats() -> None:
    with pytest.raises(AlphaVantageError, match="Unrecognized timestamp format"):
        parse_alpha_vantage_timestamp("2026-09-23 14:30")


def test_to_iso_timestamp_matches_javascript_format() -> None:
    moment = datetime(2026, 9, 23, 0, 0, 0, 123456, tzinfo=UTC)

    assert to_iso_timestamp(moment) == "2026-09-23T00:00:00.123Z"
