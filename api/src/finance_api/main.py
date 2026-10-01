"""FastAPI entry point. Run locally with `uv run fastapi dev`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from finance_api.config import get_settings
from finance_api.logging import configure_logging, request_logging_middleware
from finance_api.routes import health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Code before `yield` runs once at startup, code after it once at shutdown.
    # Loading settings here makes a missing env var fail the boot, not the first request.
    settings = get_settings()
    configure_logging(settings.log_level)

    # One client (with its connection pool) shared by every request. Creating it doesn't
    # connect yet, so the app still starts if Redis is down; /health reports it instead.
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    yield
    await app.state.redis.aclose()


app = FastAPI(title="Finance AI Assistant API", lifespan=lifespan)
app.middleware("http")(request_logging_middleware)
app.include_router(health.router)
