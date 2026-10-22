from dataclasses import dataclass

from google.genai import types


@dataclass
class Usage:
    """Token counts summed over every model call in one chat request.

    Each step re-sends the whole conversation, so input tokens are billed once per step,
    not once per request.
    """

    input_tokens: int = 0
    output_tokens: int = 0  # visible answer + thinking
    thinking_tokens: int = 0

    def add(self, usage: types.GenerateContentResponseUsageMetadata | None) -> None:
        if usage is None:
            return
        thinking = usage.thoughts_token_count or 0
        self.input_tokens += usage.prompt_token_count or 0
        self.output_tokens += (usage.candidates_token_count or 0) + thinking
        self.thinking_tokens += thinking

    def estimated_cost_usd(self, input_usd_per_mtok: float, output_usd_per_mtok: float) -> float:
        cost = (
            self.input_tokens * input_usd_per_mtok + self.output_tokens * output_usd_per_mtok
        ) / 1_000_000
        return round(cost, 6)
