from typing import Literal

import structlog
from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from redis.exceptions import RedisError

from finance_api.dependencies import RedisDep

router = APIRouter()
logger = structlog.get_logger()


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    redis: Literal["ok", "unavailable"]


@router.get("/health")
async def health(redis: RedisDep, response: Response) -> HealthResponse:
    """Readiness check for load balancers and docker-compose.

    Returns 503 when Redis is down: without it the API can't cache or throttle Alpha
    Vantage calls, so it shouldn't receive traffic.
    """
    try:
        await redis.ping()
    except RedisError as error:
        logger.warning("health_redis_unavailable", error=str(error))
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="degraded", redis="unavailable")
    return HealthResponse(status="ok", redis="ok")
