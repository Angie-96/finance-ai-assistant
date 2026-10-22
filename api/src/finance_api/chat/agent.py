"""The tool-calling loop: the Python counterpart of `streamText({ tools, stopWhen })`.

One *step* is one call to Gemini. If Gemini answers with function calls, we run the
tools, append their results to the conversation and call Gemini again. The loop stops
when Gemini answers without calling a tool, or after `max_steps` calls.

Everything that happens is yielded as protocol chunks (chat/stream.py) as soon as it
happens, so the UI shows "Fetching quote for NVDA..." while the tool is still running.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

import structlog
from google.genai import types
from pydantic import ValidationError

from finance_api.alpha_vantage import AlphaVantageClient, AlphaVantageError
from finance_api.chat.convert import encode_thought_signature
from finance_api.chat.pricing import Usage
from finance_api.chat.stream import (
    Chunk,
    FinishChunk,
    FinishReason,
    FinishStepChunk,
    StartChunk,
    StartStepChunk,
    TextDeltaChunk,
    TextEndChunk,
    TextStartChunk,
    ToolInputAvailableChunk,
    ToolInputStartChunk,
    ToolOutputAvailableChunk,
    ToolOutputErrorChunk,
)
from finance_api.tools.finance import TOOLS, ToolError, run_tool

logger = structlog.get_logger()

SYSTEM_PROMPT = (
    "You are a financial research assistant. Use tools to get real quotes, news, and "
    "price history before answering. Cite sources. "
    'Write dates in the format "Sep 23, 2026".'
)

_CONTENT_FILTER_REASONS = {
    types.FinishReason.SAFETY,
    types.FinishReason.RECITATION,
    types.FinishReason.BLOCKLIST,
    types.FinishReason.PROHIBITED_CONTENT,
    types.FinishReason.SPII,
}


class ContentStreamer(Protocol):
    """The one Gemini SDK method the loop needs (`client.aio.models` provides it).

    Typing against this instead of the SDK class lets tests pass in a scripted fake.
    """

    async def generate_content_stream(
        self, *, model: str, contents: list[types.Content], config: types.GenerateContentConfig
    ) -> AsyncIterator[types.GenerateContentResponse]: ...


@dataclass
class ChatRun:
    """What happened during one chat request, for the `chat_completed` log line."""

    steps: int = 0
    tools_called: list[str] = field(default_factory=list)
    finish_reason: str | None = None
    usage: Usage = field(default_factory=Usage)


@dataclass
class _ToolCall:
    id: str
    name: str
    args: dict[str, Any]


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _generation_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(function_declarations=[tool.declaration() for tool in TOOLS.values()])],
        # The SDK can run Python functions for us automatically. We run tools ourselves
        # so the loop, step limit, streaming and logging stay under our control.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


def _finish_reason(reason: types.FinishReason | None) -> FinishReason:
    # The frontend shows "This reply was cut off" for anything other than "stop".
    if reason == types.FinishReason.STOP:
        return "stop"
    if reason == types.FinishReason.MAX_TOKENS:
        return "length"
    if reason in _CONTENT_FILTER_REASONS:
        return "content-filter"
    return "other"


async def run_chat(
    *,
    models: ContentStreamer,
    model: str,
    contents: list[types.Content],
    alpha_vantage: AlphaVantageClient,
    max_steps: int,
    run: ChatRun,
) -> AsyncIterator[Chunk]:
    """Stream one assistant reply. `contents` is the conversation so far; it's extended
    in place with each step's model output and tool results."""
    config = _generation_config()
    yield StartChunk(message_id=_new_id("msg"))

    finish_reason: FinishReason = "tool-calls"  # kept only if the step limit is hit
    for _ in range(max_steps):
        run.steps += 1
        yield StartStepChunk()

        model_parts: list[types.Part] = []
        calls: list[_ToolCall] = []
        text_id: str | None = None
        gemini_finish: types.FinishReason | None = None
        usage: types.GenerateContentResponseUsageMetadata | None = None

        stream = await models.generate_content_stream(model=model, contents=contents, config=config)
        async for event in stream:
            # Usage counts are running totals for this call; the last one is the final.
            usage = event.usage_metadata or usage
            if not event.candidates:
                continue
            candidate = event.candidates[0]
            gemini_finish = candidate.finish_reason or gemini_finish
            parts = candidate.content.parts if candidate.content and candidate.content.parts else []

            for part in parts:
                model_parts.append(part)
                if part.function_call is not None:
                    if text_id is not None:
                        yield TextEndChunk(id=text_id)
                        text_id = None
                    call = _ToolCall(
                        id=part.function_call.id or _new_id("call"),
                        name=part.function_call.name or "",
                        args=part.function_call.args or {},
                    )
                    # Keep the id we report to the UI on the stored part, so the next
                    # step's function response matches it.
                    part.function_call.id = call.id
                    calls.append(call)
                    yield ToolInputStartChunk(tool_call_id=call.id, tool_name=call.name)
                    yield ToolInputAvailableChunk(
                        tool_call_id=call.id,
                        tool_name=call.name,
                        input=call.args,
                        # The browser keeps this and sends it back with the history; see
                        # chat/convert.py.
                        provider_metadata=(
                            {
                                "google": {
                                    "thoughtSignature": encode_thought_signature(
                                        part.thought_signature
                                    )
                                }
                            }
                            if part.thought_signature
                            else None
                        ),
                    )
                elif part.text and not part.thought:
                    if text_id is None:
                        text_id = _new_id("text")
                        yield TextStartChunk(id=text_id)
                    yield TextDeltaChunk(id=text_id, delta=part.text)

        if text_id is not None:
            yield TextEndChunk(id=text_id)
        run.usage.add(usage)
        # Gemini's turn goes back into the conversation exactly as received, so its
        # thought signatures stay attached for the next step.
        if model_parts:
            contents.append(types.Content(role="model", parts=model_parts))

        if not calls:
            finish_reason = _finish_reason(gemini_finish)
            yield FinishStepChunk()
            break

        response_parts: list[types.Part] = []
        # One at a time, in order. Alpha Vantage's throttle would serialize them anyway.
        for call in calls:
            run.tools_called.append(call.name)
            result: dict[str, Any]
            try:
                output = await run_tool(alpha_vantage, call.name, call.args)
            except Exception as error:
                message = _tool_error_message(call.name, error)
                yield ToolOutputErrorChunk(tool_call_id=call.id, error_text=message)
                result = {"error": message}
            else:
                yield ToolOutputAvailableChunk(tool_call_id=call.id, output=output)
                result = {"output": output}
            response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        id=call.id, name=call.name, response=result
                    )
                )
            )
        contents.append(types.Content(role="user", parts=response_parts))
        yield FinishStepChunk()

    run.finish_reason = finish_reason
    yield FinishChunk(finish_reason=finish_reason)


def _tool_error_message(tool_name: str, error: Exception) -> str:
    """The text the model and the UI see when a tool fails.

    Like the AI SDK, any tool failure becomes a tool error the model can react to
    ("that ticker doesn't exist, did you mean...?") instead of ending the reply.
    """
    if isinstance(error, ToolError | AlphaVantageError):
        return str(error)
    if isinstance(error, ValidationError):
        return f"Invalid arguments for {tool_name}: {error.error_count()} validation error(s)"
    # Unexpected bugs (e.g. Alpha Vantage changed its response format): log the details
    # for us, show a generic message to the user.
    logger.exception("tool_failed", tool=tool_name)
    return f"{tool_name} failed unexpectedly"
