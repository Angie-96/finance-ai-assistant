"""Convert the frontend's chat history (UIMessages) into Gemini `Content`s.

The Python counterpart of the AI SDK's `convertToModelMessages` plus the Google
provider's message conversion. Each assistant message can hold several *steps* (separated
by "step-start" parts): a step is one model call, made of text and/or function calls,
followed by our function responses. Gemini expects exactly that shape:

    user:  "What's NVDA at?"
    model: functionCall getQuote({"symbol": "NVDA"})      <- step 1
    user:  functionResponse getQuote({"output": {...}})
    model: "NVDA is trading at $178.43..."                <- step 2
"""

import base64
from typing import Any

from google.genai import types

from finance_api.schemas.ui import TextUIPart, ToolUIPart, UIMessage

# Gemini 3 attaches an encrypted "thought signature" to function calls and requires it
# back when the history is resent; a function call without one is rejected. This value,
# which Google documents for history whose signatures are unavailable, skips that check.
# (Same value the AI SDK's Google provider uses.)
SKIP_THOUGHT_SIGNATURE = "skip_thought_signature_validator"

# Tool calls that never finished (e.g. the user stopped the reply) have no result to
# send back, and Gemini requires every function call to be followed by a response.
_FINISHED_TOOL_STATES = {"output-available", "output-error"}


def encode_thought_signature(signature: bytes) -> str:
    """Bytes -> text, so the signature can travel through the browser as JSON."""
    return base64.urlsafe_b64encode(signature).decode("ascii")


def decode_thought_signature(encoded: str) -> bytes:
    # The SDK base64-encodes bytes with the URL-safe alphabet when it builds the request,
    # so decoding the same way makes the skip value above arrive exactly as written.
    return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))


def to_gemini_contents(messages: list[UIMessage]) -> list[types.Content]:
    contents: list[types.Content] = []
    for message in messages:
        if message.role == "user":
            texts = [p["text"] for p in message.parts if p.get("type") == "text" and p.get("text")]
            if texts:
                contents.append(
                    types.Content(role="user", parts=[types.Part(text=t) for t in texts])
                )
        elif message.role == "assistant":
            for step in _split_steps(message.parts):
                contents.extend(_step_to_contents(step))
        # "system" messages from the client are ignored on purpose: the server owns the
        # system prompt, so a client can't replace the assistant's instructions.
    return contents


def _split_steps(parts: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    steps: list[list[dict[str, Any]]] = [[]]
    for part in parts:
        if part.get("type") == "step-start":
            steps.append([])
        else:
            steps[-1].append(part)
    return [step for step in steps if step]


def _step_to_contents(step: list[dict[str, Any]]) -> list[types.Content]:
    model_parts: list[types.Part] = []
    response_parts: list[types.Part] = []
    has_signed_call = False

    for raw in step:
        part_type = str(raw.get("type", ""))
        if part_type == "text":
            text = TextUIPart.model_validate(raw).text
            if text:
                model_parts.append(types.Part(text=text))
        elif part_type.startswith("tool-"):
            tool = ToolUIPart.model_validate(raw)
            if tool.state not in _FINISHED_TOOL_STATES:
                continue

            signature = _thought_signature(tool)
            if signature is None and not has_signed_call:
                signature = SKIP_THOUGHT_SIGNATURE
            # When Gemini makes several calls at once, only the first carries the
            # signature; the rest correctly have none.
            has_signed_call = has_signed_call or signature is not None

            model_parts.append(
                types.Part(
                    function_call=types.FunctionCall(
                        id=tool.tool_call_id, name=tool.tool_name, args=tool.input or {}
                    ),
                    thought_signature=decode_thought_signature(signature) if signature else None,
                )
            )
            # Google's convention: success under "output", failure under "error".
            response = (
                {"output": tool.output}
                if tool.state == "output-available"
                else {"error": tool.error_text or "Tool call failed."}
            )
            response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        id=tool.tool_call_id, name=tool.tool_name, response=response
                    )
                )
            )
        # Other part types ("reasoning", "file", "data-*", ...) aren't produced by this
        # app and are skipped.

    contents = []
    if model_parts:
        contents.append(types.Content(role="model", parts=model_parts))
    if response_parts:
        contents.append(types.Content(role="user", parts=response_parts))
    return contents


def _thought_signature(tool: ToolUIPart) -> str | None:
    google = (tool.call_provider_metadata or {}).get("google") or {}
    signature = google.get("thoughtSignature")
    return signature if isinstance(signature, str) and signature else None
