"""Structured (JSON) logging and per-request log context.

Every log line is one JSON object, so a log platform can filter and aggregate on fields
(e.g. all requests with status 500, or average latency_ms) instead of parsing text.
"""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response

logger = structlog.get_logger()

REQUEST_ID_HEADER = "X-Request-ID"


def configure_logging(level: str) -> None:
    structlog.configure(
        processors=[
            # Pulls in fields bound with bind_contextvars(), e.g. request_id, so every
            # log line written while handling a request carries them automatically.
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level.upper())),
    )


async def request_logging_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Tag the request with an ID and log one `request` line when it completes.

    Note: for streaming responses, latency_ms is the time until the response *starts*.
    The chat endpoint logs its own end-to-end latency once the stream finishes.
    """
    # Reuse the caller's ID when given (e.g. from the Next.js proxy) so one request can
    # be traced across services; otherwise make a new one.
    request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id, method=request.method, path=request.url.path
    )

    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed")
        raise
    latency_ms = round((time.perf_counter() - start) * 1000, 1)

    response.headers[REQUEST_ID_HEADER] = request_id
    logger.info("request", status=response.status_code, latency_ms=latency_ms)
    return response
