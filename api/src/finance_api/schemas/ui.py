"""The request body the frontend's `useChat` (DefaultChatTransport) sends to /chat.

Mirrors AI SDK v7's UIMessage (web/node_modules/ai/src/ui/ui-messages.ts). Only the
fields the API uses are declared; unknown fields are ignored, so newer SDK versions
adding fields won't break parsing.
"""

from typing import Any, Literal

from finance_api.schemas.base import CamelModel


class UIMessage(CamelModel):
    id: str
    role: Literal["system", "user", "assistant"]
    # Kept as raw dicts: a part's shape depends on its `type` ("text", "step-start",
    # "tool-getQuote", ...). chat/convert.py reads the ones it needs.
    parts: list[dict[str, Any]]


class ChatRequest(CamelModel):
    id: str | None = None  # chat id
    messages: list[UIMessage]
    trigger: Literal["submit-message", "regenerate-message"] | None = None
    message_id: str | None = None


class TextUIPart(CamelModel):
    type: Literal["text"]
    text: str


class ToolUIPart(CamelModel):
    """A tool call as the UI stored it: `type` is "tool-<name>", e.g. "tool-getQuote"."""

    type: str
    tool_call_id: str
    state: str  # "input-streaming" | "input-available" | "output-available" | "output-error" | ...
    input: Any = None
    output: Any = None
    error_text: str | None = None
    # Whatever we sent as `providerMetadata` on tool-input-available; useChat stores it
    # here and sends it back. Holds the Gemini thought signature.
    call_provider_metadata: dict[str, Any] | None = None

    @property
    def tool_name(self) -> str:
        return self.type.removeprefix("tool-")
