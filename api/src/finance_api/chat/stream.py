"""Encoder for the Vercel AI SDK "UI message stream" protocol (v1).

This is what lets the frontend's `useChat` read a Python response as if `streamText` had
produced it. The stream is Server-Sent Events: one `data: {json}\\n\\n` line per chunk,
ending with `data: [DONE]`.

Source of truth for chunk names and fields (AI SDK 7.0.x):
- docs:   web/node_modules/ai/docs/04-ai-sdk-ui/50-stream-protocol.mdx
- schema: web/node_modules/ai/src/ui-message-stream/ui-message-chunks.ts
"""

from typing import Any, Literal

from finance_api.schemas.base import CamelModel

# From ai/src/ui-message-stream/ui-message-stream-headers.ts. The last header stops
# proxies like nginx from buffering the stream into one late blob.
UI_MESSAGE_STREAM_HEADERS = {
    "content-type": "text/event-stream",
    "cache-control": "no-cache",
    "connection": "keep-alive",
    "x-vercel-ai-ui-message-stream": "v1",
    "x-accel-buffering": "no",
}

SSE_DONE = "data: [DONE]\n\n"

FinishReason = Literal["stop", "length", "content-filter", "tool-calls", "error", "other"]


class Chunk(CamelModel):
    """Base class: every chunk has a `type`, and fields left as None are omitted."""

    type: str

    def to_sse(self) -> str:
        return f"data: {self.model_dump_json(exclude_none=True)}\n\n"


class StartChunk(Chunk):
    type: Literal["start"] = "start"
    message_id: str | None = None


class StartStepChunk(Chunk):
    """Start of one model call. Each tool round is its own step."""

    type: Literal["start-step"] = "start-step"


class FinishStepChunk(Chunk):
    type: Literal["finish-step"] = "finish-step"


class TextStartChunk(Chunk):
    type: Literal["text-start"] = "text-start"
    id: str


class TextDeltaChunk(Chunk):
    type: Literal["text-delta"] = "text-delta"
    id: str
    delta: str


class TextEndChunk(Chunk):
    type: Literal["text-end"] = "text-end"
    id: str


class ToolInputStartChunk(Chunk):
    type: Literal["tool-input-start"] = "tool-input-start"
    tool_call_id: str
    tool_name: str


class ToolInputAvailableChunk(Chunk):
    type: Literal["tool-input-available"] = "tool-input-available"
    tool_call_id: str
    tool_name: str
    input: dict[str, Any]
    provider_metadata: dict[str, dict[str, Any]] | None = None


class ToolOutputAvailableChunk(Chunk):
    type: Literal["tool-output-available"] = "tool-output-available"
    tool_call_id: str
    output: Any


class ToolOutputErrorChunk(Chunk):
    type: Literal["tool-output-error"] = "tool-output-error"
    tool_call_id: str
    error_text: str


class FinishChunk(Chunk):
    type: Literal["finish"] = "finish"
    # The frontend shows "This reply was cut off" for anything other than "stop".
    finish_reason: FinishReason | None = None


class ErrorChunk(Chunk):
    type: Literal["error"] = "error"
    error_text: str
