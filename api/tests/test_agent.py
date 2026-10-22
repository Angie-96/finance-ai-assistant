"""Agent loop tests with a scripted Gemini (tests/fakes.py): no real model calls."""

import json
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from finance_api.chat.agent import ChatRun, ContentStreamer, run_chat
from finance_api.chat.convert import encode_thought_signature
from finance_api.chat.stream import Chunk
from tests.fakes import FakeAlphaVantage, FakeGemini, call_response, text_response

FIXTURES = Path(__file__).parent / "fixtures"
QUOTE = json.loads((FIXTURES / "global_quote.json").read_text())


def question(text: str = "What's NVDA at?") -> list[types.Content]:
    return [types.Content(role="user", parts=[types.Part(text=text)])]


async def collect(
    gemini: FakeGemini, av: FakeAlphaVantage | None = None, max_steps: int = 5
) -> tuple[list[dict[str, Any]], ChatRun]:
    run = ChatRun()
    chunks: list[Chunk] = [
        chunk
        async for chunk in run_chat(
            models=gemini,
            model="gemini-test",
            contents=question(),
            alpha_vantage=av or FakeAlphaVantage({"GLOBAL_QUOTE": QUOTE}),
            max_steps=max_steps,
            run=run,
        )
    ]
    return [chunk.model_dump(exclude_none=True) for chunk in chunks], run


def types_of(chunks: list[dict[str, Any]]) -> list[str]:
    return [chunk["type"] for chunk in chunks]


def test_the_real_sdk_matches_the_interface_the_loop_expects() -> None:
    # Checked by mypy, not at runtime: if the SDK's method signature changes, this
    # assignment stops type-checking.
    real: ContentStreamer = genai.Client(api_key="unused").aio.models
    assert real is not None


async def test_plain_answer_streams_text_and_finishes_with_stop() -> None:
    gemini = FakeGemini(
        [[text_response("Hello"), text_response(" there", types.FinishReason.STOP, (10, 2, 0))]]
    )

    chunks, run = await collect(gemini)

    assert types_of(chunks) == [
        "start",
        "start-step",
        "text-start",
        "text-delta",
        "text-delta",
        "text-end",
        "finish-step",
        "finish",
    ]
    assert [c["delta"] for c in chunks if c["type"] == "text-delta"] == ["Hello", " there"]
    assert chunks[-1]["finishReason"] == "stop"
    assert run.steps == 1
    assert run.finish_reason == "stop"


async def test_tool_call_then_answer() -> None:
    gemini = FakeGemini(
        [
            [call_response(("getQuote", {"symbol": "NVDA"}), usage=(100, 10, 30))],
            [text_response("NVDA is at $178.43.", types.FinishReason.STOP, (200, 20, 0))],
        ]
    )

    chunks, run = await collect(gemini)

    assert types_of(chunks) == [
        "start",
        "start-step",
        "tool-input-start",
        "tool-input-available",
        "tool-output-available",
        "finish-step",
        "start-step",
        "text-start",
        "text-delta",
        "text-end",
        "finish-step",
        "finish",
    ]
    tool_input = chunks[3]
    assert tool_input["toolName"] == "getQuote"
    assert tool_input["input"] == {"symbol": "NVDA"}
    assert tool_input["providerMetadata"] == {
        "google": {"thoughtSignature": encode_thought_signature(b"sig")}
    }
    output = chunks[4]
    assert output["toolCallId"] == tool_input["toolCallId"]
    assert output["output"]["price"] == 178.43
    assert run.tools_called == ["getQuote"]
    assert run.steps == 2
    assert (run.usage.input_tokens, run.usage.output_tokens) == (300, 60)


async def test_second_call_sends_the_tool_result_and_keeps_the_signature() -> None:
    gemini = FakeGemini(
        [
            [call_response(("getQuote", {"symbol": "NVDA"}))],
            [text_response("Done", types.FinishReason.STOP)],
        ]
    )

    await collect(gemini)

    _question, model_turn, tool_results = gemini.requests[1]
    assert model_turn.role == "model"
    call_part = model_turn.parts[0]  # type: ignore[index]
    assert call_part.thought_signature == b"sig"  # resent exactly as Gemini sent it
    result = tool_results.parts[0].function_response  # type: ignore[index]
    assert result is not None
    assert result.id == call_part.function_call.id  # type: ignore[union-attr]
    assert result.response is not None
    assert result.response["output"]["symbol"] == "NVDA"


async def test_tool_errors_go_to_the_ui_and_back_to_the_model() -> None:
    gemini = FakeGemini(
        [
            [call_response(("getQuote", {"symbol": "ZZZZ"}))],
            [text_response("I couldn't find ZZZZ.", types.FinishReason.STOP)],
        ]
    )

    chunks, _ = await collect(gemini, FakeAlphaVantage({}))

    [error] = [c for c in chunks if c["type"] == "tool-output-error"]
    assert error["errorText"] == "No quote data found for ZZZZ"
    result = gemini.requests[1][2].parts[0].function_response  # type: ignore[index]
    assert result is not None
    assert result.response == {"error": "No quote data found for ZZZZ"}
    assert chunks[-1]["finishReason"] == "stop"  # the reply continues after the error


async def test_unexpected_tool_failures_show_a_generic_message() -> None:
    broken_quote = {"Global Quote": {"05. price": "1.0"}}  # missing the other fields
    gemini = FakeGemini(
        [
            [call_response(("getQuote", {"symbol": "NVDA"}))],
            [text_response("Sorry.", types.FinishReason.STOP)],
        ]
    )

    chunks, _ = await collect(gemini, FakeAlphaVantage({"GLOBAL_QUOTE": broken_quote}))

    [error] = [c for c in chunks if c["type"] == "tool-output-error"]
    assert error["errorText"] == "getQuote failed unexpectedly"


async def test_parallel_calls_run_in_order() -> None:
    gemini = FakeGemini(
        [
            [call_response(("getQuote", {"symbol": "NVDA"}), ("getNews", {"symbol": "NVDA"}))],
            [text_response("Here you go.", types.FinishReason.STOP)],
        ]
    )

    chunks, run = await collect(gemini)

    assert run.tools_called == ["getQuote", "getNews"]
    second_input = [c for c in chunks if c["type"] == "tool-input-available"][1]
    assert "providerMetadata" not in second_input  # Gemini signs only the first call


async def test_step_limit_stops_a_model_that_keeps_calling_tools() -> None:
    looping = [[call_response(("getQuote", {"symbol": "NVDA"}))] for _ in range(10)]
    gemini = FakeGemini(looping)

    chunks, run = await collect(gemini, max_steps=3)

    assert len(gemini.requests) == 3
    assert run.steps == 3
    assert chunks[-1] == {"type": "finish", "finishReason": "tool-calls"}


async def test_max_tokens_is_reported_as_length() -> None:
    gemini = FakeGemini([[text_response("Partial", types.FinishReason.MAX_TOKENS)]])

    chunks, _ = await collect(gemini)

    assert chunks[-1]["finishReason"] == "length"  # the UI shows "cut off"


async def test_text_before_a_tool_call_is_closed_first() -> None:
    gemini = FakeGemini(
        [
            [text_response("Let me check."), call_response(("getQuote", {"symbol": "NVDA"}))],
            [text_response("Done", types.FinishReason.STOP)],
        ]
    )

    chunks, _ = await collect(gemini)

    assert types_of(chunks)[2:6] == ["text-start", "text-delta", "text-end", "tool-input-start"]
