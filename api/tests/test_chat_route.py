"""POST /chat end to end through FastAPI, with fake Gemini and Alpha Vantage."""

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from google.genai import errors as genai_errors
from google.genai import types
from structlog.testing import capture_logs

from finance_api.dependencies import get_alpha_vantage, get_gemini
from finance_api.main import app
from tests.fakes import FailingGemini, FakeAlphaVantage, FakeGemini, call_response, text_response
from tests.test_agent import QUOTE

BODY = {
    "id": "chat_1",
    "messages": [
        {"id": "m1", "role": "user", "parts": [{"type": "text", "text": "What's NVDA at?"}]}
    ],
    "trigger": "submit-message",
}


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_alpha_vantage] = lambda: FakeAlphaVantage({"GLOBAL_QUOTE": QUOTE})
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def parse_sse(text: str) -> tuple[list[dict[str, Any]], str]:
    """Split an SSE body into its JSON chunks and the final line."""
    events = [line.removeprefix("data: ") for line in text.split("\n\n") if line]
    return [json.loads(event) for event in events[:-1]], events[-1]


def test_streams_a_full_reply_in_the_ui_message_protocol(client: TestClient) -> None:
    app.dependency_overrides[get_gemini] = lambda: FakeGemini(
        [
            [call_response(("getQuote", {"symbol": "NVDA"}), usage=(1000, 50, 100))],
            [text_response("NVDA is at $178.43.", types.FinishReason.STOP, (2000, 30, 0))],
        ]
    )

    with capture_logs() as logs:
        response = client.post("/chat", json=BODY)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-vercel-ai-ui-message-stream"] == "v1"
    chunks, last = parse_sse(response.text)
    assert last == "[DONE]"
    assert chunks[0]["type"] == "start"
    assert chunks[-1] == {"type": "finish", "finishReason": "stop"}

    [completed] = [log for log in logs if log["event"] == "chat_completed"]
    assert completed["tools_called"] == ["getQuote"]
    assert completed["steps"] == 2
    assert completed["finish_reason"] == "stop"
    assert completed["input_tokens"] == 3000
    assert completed["output_tokens"] == 180
    # 3000 x $0.75/M + 180 x $3.75/M
    assert completed["estimated_cost_usd"] == pytest.approx(0.002925)


def test_gemini_errors_are_streamed_with_their_message(client: TestClient) -> None:
    quota = genai_errors.ClientError(
        429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "Quota exceeded"}}
    )
    app.dependency_overrides[get_gemini] = lambda: FailingGemini(quota)

    with capture_logs() as logs:
        response = client.post("/chat", json=BODY)

    chunks, last = parse_sse(response.text)
    error = chunks[-1]
    assert error["type"] == "error"
    # Chat.tsx matches /quota|rate limit|resource.?exhausted/ to show its quota notice.
    assert error["errorText"] == "429 RESOURCE_EXHAUSTED: Quota exceeded"
    assert last == "[DONE]"
    [completed] = [log for log in logs if log["event"] == "chat_completed"]
    assert completed["finish_reason"] == "error"


def test_unexpected_errors_do_not_leak_details(client: TestClient) -> None:
    app.dependency_overrides[get_gemini] = lambda: FailingGemini(RuntimeError("secret internals"))

    response = client.post("/chat", json=BODY)

    chunks, _ = parse_sse(response.text)
    assert chunks[-1] == {"type": "error", "errorText": "An error occurred."}


def test_invalid_body_is_rejected(client: TestClient) -> None:
    response = client.post("/chat", json={"messages": "not a list"})

    assert response.status_code == 422
