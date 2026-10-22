"""Test doubles for the two external services: Alpha Vantage and Gemini."""

from collections.abc import AsyncIterator, Mapping
from typing import Any

from google.genai import types

from finance_api.alpha_vantage import AlphaVantageClient


class FakeAlphaVantage(AlphaVantageClient):
    """Returns canned responses and records the params each call was made with.

    `responses` maps an Alpha Vantage `function` (e.g. "GLOBAL_QUOTE") to its response.
    """

    def __init__(self, responses: Mapping[str, dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, str]] = []

    async def request(self, params: Mapping[str, str]) -> dict[str, Any]:
        self.calls.append(dict(params))
        return self.responses.get(params["function"], {})


class FakeGemini:
    """Plays back scripted model calls. Each item in `steps` is the list of streamed
    responses for one call to generate_content_stream (one agent step)."""

    def __init__(self, steps: list[list[types.GenerateContentResponse]]) -> None:
        self.steps = steps
        self.requests: list[list[types.Content]] = []  # the conversation sent each time

    async def generate_content_stream(
        self, *, model: str, contents: list[types.Content], config: types.GenerateContentConfig
    ) -> AsyncIterator[types.GenerateContentResponse]:
        self.requests.append(list(contents))  # copy: the agent extends this list
        responses = self.steps[len(self.requests) - 1]

        async def stream() -> AsyncIterator[types.GenerateContentResponse]:
            for response in responses:
                yield response

        return stream()


class FailingGemini:
    """Raises the given error on the first call, like a quota or network failure."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    async def generate_content_stream(
        self, *, model: str, contents: list[types.Content], config: types.GenerateContentConfig
    ) -> AsyncIterator[types.GenerateContentResponse]:
        raise self.error


def text_response(
    text: str,
    finish_reason: types.FinishReason | None = None,
    usage: tuple[int, int, int] | None = None,
) -> types.GenerateContentResponse:
    """One streamed chunk of text. `usage` is (input, output, thinking) tokens."""
    return _response([types.Part(text=text)], finish_reason, usage)


def call_response(
    *calls: tuple[str, dict[str, Any]],
    signature: bytes | None = b"sig",
    usage: tuple[int, int, int] | None = None,
) -> types.GenerateContentResponse:
    """A chunk with function calls; like Gemini 3, only the first carries a signature."""
    parts = [
        types.Part(
            function_call=types.FunctionCall(name=name, args=args),
            thought_signature=signature if index == 0 else None,
        )
        for index, (name, args) in enumerate(calls)
    ]
    return _response(parts, types.FinishReason.STOP, usage)


def _response(
    parts: list[types.Part],
    finish_reason: types.FinishReason | None,
    usage: tuple[int, int, int] | None,
) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=parts), finish_reason=finish_reason
            )
        ],
        usage_metadata=(
            types.GenerateContentResponseUsageMetadata(
                prompt_token_count=usage[0],
                candidates_token_count=usage[1],
                thoughts_token_count=usage[2],
            )
            if usage
            else None
        ),
    )
