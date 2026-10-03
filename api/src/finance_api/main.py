"""FastAPI entry point. Run locally with `uv run fastapi dev`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis

from finance_api.alpha_vantage import AlphaVantageClient
from finance_api.config import get_settings
from finance_api.logging import configure_logging, request_logging_middleware
from finance_api.routes import health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Code before `yield` runs once at startup, code after it once at shutdown.
    # Loading settings here makes a missing env var fail the boot, not the first request.
    settings = get_settings()
    configure_logging(settings.log_level)

    # Long-lived clients with connection pools, shared by every request. Creating them
    # doesn't connect yet, so the app still starts if Redis is down; /health reports it.
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    http = httpx.AsyncClient(timeout=10.0)
    app.state.redis = redis
    app.state.alpha_vantage = AlphaVantageClient(
        http, redis, settings.alpha_vantage_api_key.get_secret_value()
    )
    yield
    await http.aclose()
    await redis.aclose()


app = FastAPI(title="Finance AI Assistant API", lifespan=lifespan)
app.middleware("http")(request_logging_middleware)
app.include_router(health.router)
