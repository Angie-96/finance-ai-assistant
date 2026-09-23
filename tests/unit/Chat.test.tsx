import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Chat } from "@/components/chat/Chat";

describe("Chat", () => {
  it("renders the header and suggestion prompts when there are no messages yet", () => {
    render(<Chat />);

    expect(
      screen.getByRole("heading", { name: /finance research assistant/i }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: /what's the latest quote for nvda/i }),
    ).toBeInTheDocument();
  });
});
