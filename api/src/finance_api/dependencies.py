"""Shared objects handed to route functions via FastAPI's `Depends`.

Routes ask for what they need (`redis: RedisDep`) instead of importing globals. In tests,
`app.dependency_overrides` swaps the real object for a fake one.
"""

from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis


def get_redis(request: Request) -> Redis:
    # Created once at startup in main.lifespan and stored on app.state.
    redis: Redis = request.app.state.redis
    return redis


RedisDep = Annotated[Redis, Depends(get_redis)]
