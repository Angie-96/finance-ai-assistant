import json

import pytest

from finance_api.chat.stream import (
    SSE_DONE,
    UI_MESSAGE_STREAM_HEADERS,
    Chunk,
    ErrorChunk,
    FinishChunk,
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

# Required and optional fields per chunk type, copied from the AI SDK's validation schema
# (web/node_modules/ai/src/ui-message-stream/ui-message-chunks.ts). useChat rejects
# chunks that don't match, so this pins our output to the real contract.
SDK_CHUNK_FIELDS: dict[str, tuple[set[str], set[str]]] = {
    "start": (set(), {"messageId", "messageMetadata"}),
    "start-step": (set(), set()),
    "finish-step": (set(), set()),
    "text-start": ({"id"}, {"providerMetadata"}),
    "text-delta": ({"id", "delta"}, {"providerMetadata"}),
    "text-end": ({"id"}, {"providerMetadata"}),
    "tool-input-start": ({"toolCallId", "toolName"}, {"providerMetadata", "dynamic", "title"}),
    "tool-input-available": (
        {"toolCallId", "toolName", "input"},
        {"providerMetadata", "dynamic", "title"},
    ),
    "tool-output-available": ({"toolCallId", "output"}, {"providerMetadata", "preliminary"}),
    "tool-output-error": ({"toolCallId", "errorText"}, {"providerMetadata"}),
    "finish": (set(), {"finishReason", "messageMetadata"}),
    "error": ({"errorText"}, set()),
}

EXAMPLE_CHUNKS: list[Chunk] = [
    StartChunk(message_id="msg_1"),
    StartStepChunk(),
    TextStartChunk(id="t1"),
    TextDeltaChunk(id="t1", delta="Hello"),
    TextEndChunk(id="t1"),
    ToolInputStartChunk(tool_call_id="call_1", tool_name="getQuote"),
    ToolInputAvailableChunk(
        tool_call_id="call_1",
        tool_name="getQuote",
        input={"symbol": "NVDA"},
        provider_metadata={"google": {"thoughtSignature": "c2ln"}},
    ),
    ToolOutputAvailableChunk(tool_call_id="call_1", output={"price": 1.0, "asOf": None}),
    ToolOutputErrorChunk(tool_call_id="call_2", error_text="No quote data found for ZZZZ"),
    FinishStepChunk(),
    FinishChunk(finish_reason="stop"),
    ErrorChunk(error_text="boom"),
]


def decode(sse: str) -> dict[str, object]:
    assert sse.startswith("data: ")
    assert sse.endswith("\n\n")
    data: dict[str, object] = json.loads(sse.removeprefix("data: "))
    return data


@pytest.mark.parametrize("chunk", EXAMPLE_CHUNKS, ids=lambda chunk: chunk.type)
def test_chunks_match_the_ai_sdk_schema(chunk: Chunk) -> None:
    data = decode(chunk.to_sse())

    chunk_type = str(data.pop("type"))
    required, optional = SDK_CHUNK_FIELDS[chunk_type]
    assert required <= data.keys(), f"missing {required - data.keys()}"
    assert data.keys() <= required | optional, f"unexpected {data.keys() - required - optional}"


def test_chunk_fields_are_camel_case_and_unset_fields_are_omitted() -> None:
    assert decode(ToolOutputErrorChunk(tool_call_id="c", error_text="e").to_sse()) == {
        "type": "tool-output-error",
        "toolCallId": "c",
        "errorText": "e",
    }
    assert decode(StartChunk().to_sse()) == {"type": "start"}


def test_tool_output_is_sent_as_is() -> None:
    # Output keys are already the frontend's camelCase, and nulls inside it are kept.
    chunk = ToolOutputAvailableChunk(tool_call_id="c", output={"changePercent": 1.5, "x": None})

    assert decode(chunk.to_sse())["output"] == {"changePercent": 1.5, "x": None}


def test_stream_ends_with_done_marker() -> None:
    assert SSE_DONE == "data: [DONE]\n\n"


def test_headers_declare_the_ui_message_stream_protocol() -> None:
    assert UI_MESSAGE_STREAM_HEADERS["content-type"] == "text/event-stream"
    assert UI_MESSAGE_STREAM_HEADERS["x-vercel-ai-ui-message-stream"] == "v1"
