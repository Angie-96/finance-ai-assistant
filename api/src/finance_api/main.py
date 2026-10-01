"""FastAPI entry point. Run locally with `uv run fastapi dev`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from finance_api.config import get_settings
from finance_api.routes import health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Code before `yield` runs once at startup, code after it once at shutdown.
    # Loading settings here makes a missing env var fail the boot, not the first request.
    get_settings()
    yield


app = FastAPI(title="Finance AI Assistant API", lifespan=lifespan)
app.include_router(health.router)
