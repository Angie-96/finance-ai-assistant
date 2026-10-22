import time
from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from google.genai import errors as genai_errors

from finance_api.alpha_vantage import AlphaVantageClient, AlphaVantageError
from finance_api.chat.agent import ChatRun, ContentStreamer, run_chat
from finance_api.chat.convert import to_gemini_contents
from finance_api.chat.stream import SSE_DONE, UI_MESSAGE_STREAM_HEADERS, ErrorChunk
from finance_api.config import Settings
from finance_api.dependencies import AlphaVantageDep, GeminiDep, SettingsDep
from finance_api.schemas.ui import ChatRequest

router = APIRouter()
logger = structlog.get_logger()


@router.post("/chat")
async def chat(
    body: ChatRequest, alpha_vantage: AlphaVantageDep, gemini: GeminiDep, settings: SettingsDep
) -> StreamingResponse:
    """Accepts `useChat`'s request body and streams the reply in the UI message stream
    protocol, so the frontend can't tell it apart from the AI SDK's `streamText`."""
    return StreamingResponse(
        _stream(body, alpha_vantage, gemini, settings),
        headers=UI_MESSAGE_STREAM_HEADERS,
        media_type="text/event-stream",
    )


async def _stream(
    body: ChatRequest,
    alpha_vantage: AlphaVantageClient,
    gemini: ContentStreamer,
    settings: Settings,
) -> AsyncIterator[str]:
    run = ChatRun()
    start = time.perf_counter()
    try:
        async for chunk in run_chat(
            models=gemini,
            model=settings.gemini_model,
            contents=to_gemini_contents(body.messages),
            alpha_vantage=alpha_vantage,
            max_steps=settings.max_steps,
            run=run,
        ):
            yield chunk.to_sse()
    except Exception as error:
        # The HTTP status (200) is already sent once streaming starts, so errors are
        # reported in-stream. useChat turns this chunk into its `error` state.
        run.finish_reason = "error"
        logger.exception("chat_failed")
        yield ErrorChunk(error_text=_error_message(error)).to_sse()
    finally:
        # Runs on success, on error, and when the client disconnects mid-stream (then
        # finish_reason stays None and shows up as "aborted").
        logger.info(
            "chat_completed",
            model=settings.gemini_model,
            steps=run.steps,
            tools_called=run.tools_called,
            finish_reason=run.finish_reason or "aborted",
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
            input_tokens=run.usage.input_tokens,
            output_tokens=run.usage.output_tokens,
            thinking_tokens=run.usage.thinking_tokens,
            estimated_cost_usd=run.usage.estimated_cost_usd(
                settings.gemini_input_usd_per_mtok, settings.gemini_output_usd_per_mtok
            ),
        )
    yield SSE_DONE


def _error_message(error: Exception) -> str:
    # Gemini's own message is kept: the frontend looks for "quota" / "resource exhausted"
    # in it to show its "free-tier limit reached" notice. Anything else stays generic so
    # internals don't leak to the browser.
    if isinstance(error, genai_errors.APIError):
        return f"{error.code} {error.status}: {error.message}"  # "429 RESOURCE_EXHAUSTED: ..."
    if isinstance(error, AlphaVantageError):
        return str(error)
    return "An error occurred."
