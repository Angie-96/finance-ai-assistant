"""The only code that talks to Alpha Vantage. Tools must go through AlphaVantageClient.

Two protections, both stored in Redis so they hold across every running API instance:

- Cache: responses are kept for 5 minutes, so repeat questions don't spend quota
  (the free tier allows about 25 requests a day).
- Throttle: calls are spaced at least 1.5 s apart. The free tier allows 1 request per
  second, and the model often calls several tools in one turn.

In-process memory (what the TypeScript version used) only protects a single process.
With two instances, each would have its own cache and its own throttle, and together
they could exceed the rate limit.
"""

import asyncio
import hashlib
import json
import re
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx
from redis.asyncio import Redis

BASE_URL = "https://www.alphavantage.co/query"
CACHE_KEY_PREFIX = "av:cache:"
THROTTLE_KEY = "av:throttle"
# Alpha Vantage reports problems (bad symbol, rate limit, invalid key) with HTTP 200
# and one of these keys in the body.
ERROR_KEYS = ("Error Message", "Note", "Information")


class AlphaVantageError(Exception):
    """Alpha Vantage couldn't answer. The message is safe to show to the model and user."""


class AlphaVantageClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        redis: Redis,
        api_key: str,
        *,
        cache_ttl_seconds: int = 5 * 60,
        min_interval_ms: int = 1500,
        throttle_timeout_seconds: float = 30.0,
    ) -> None:
        self._http = http
        self._redis = redis
        self._api_key = api_key
        self._cache_ttl_seconds = cache_ttl_seconds
        self._min_interval_ms = min_interval_ms
        self._throttle_timeout_seconds = throttle_timeout_seconds

    async def request(self, params: Mapping[str, str]) -> dict[str, Any]:
        """Call Alpha Vantage with `params` (without the API key) and return the JSON body."""
        cache_key = _cache_key(params)
        cached = await self._redis.get(cache_key)
        if cached is not None:
            data: dict[str, Any] = json.loads(cached)
            return data

        await self._wait_for_slot()
        try:
            response = await self._http.get(BASE_URL, params={**params, "apikey": self._api_key})
        except httpx.HTTPError as error:
            # Only the exception type: some httpx messages include the URL, which
            # contains the API key.
            raise AlphaVantageError(
                f"Alpha Vantage request failed ({type(error).__name__})"
            ) from error

        if response.is_error:
            raise AlphaVantageError(
                f"Alpha Vantage request failed with status {response.status_code}"
            )

        data = response.json()
        if not isinstance(data, dict):
            raise AlphaVantageError("Alpha Vantage returned an unexpected response")
        for key in ERROR_KEYS:
            if isinstance(data.get(key), str):
                raise AlphaVantageError(data[key])

        # Only successful responses are cached, so a rate-limit note isn't replayed
        # for 5 minutes.
        await self._redis.set(cache_key, json.dumps(data), ex=self._cache_ttl_seconds)
        return data

    async def _wait_for_slot(self) -> None:
        """Block until this caller may send a request, across all API instances.

        `SET key NX PX 1500` only succeeds if the key doesn't exist, and the key expires
        after 1.5 s. Whoever sets it owns the next slot; everyone else waits until it
        expires and tries again. Redis runs commands one at a time, so two instances can
        never both win the same slot.
        """
        deadline = time.monotonic() + self._throttle_timeout_seconds
        while not await self._redis.set(THROTTLE_KEY, "1", nx=True, px=self._min_interval_ms):
            # Milliseconds until the current slot expires. Negative if the key vanished
            # between our two commands; then retry almost immediately.
            remaining_ms = await self._redis.pttl(THROTTLE_KEY)
            wait_seconds = max(remaining_ms, 10) / 1000
            if time.monotonic() + wait_seconds > deadline:
                raise AlphaVantageError("Alpha Vantage is busy, please retry in a moment")
            await asyncio.sleep(wait_seconds)


def _cache_key(params: Mapping[str, str]) -> str:
    # Sorted so {"a","b"} and {"b","a"} share an entry. Hashed to keep keys short.
    # The API key is never part of it (it's added after this, at request time).
    canonical = urlencode(sorted(params.items()))
    return CACHE_KEY_PREFIX + hashlib.sha256(canonical.encode()).hexdigest()


def to_iso_timestamp(moment: datetime) -> str:
    """Format like JavaScript's Date.toISOString(): "2026-09-23T14:30:00.000Z"."""
    return (
        moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"
    )


_TIMESTAMP_PATTERN = re.compile(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})$")


def parse_alpha_vantage_timestamp(raw: str) -> str:
    """Convert Alpha Vantage's "20260923T143000" (UTC) to an ISO 8601 string."""
    match = _TIMESTAMP_PATTERN.match(raw)
    if match is None:
        raise AlphaVantageError(f"Unrecognized timestamp format: {raw}")
    year, month, day, hour, minute, second = (int(part) for part in match.groups())
    return to_iso_timestamp(datetime(year, month, day, hour, minute, second, tzinfo=UTC))
