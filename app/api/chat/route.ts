import { google } from "@ai-sdk/google";
import {
  streamText,
  convertToModelMessages,
  toUIMessageStream,
  createUIMessageStreamResponse,
  type UIMessage,
} from "ai";
import {
  getQuote,
  getNews,
  getHistoricalPrices,
} from "@/lib/tools/finance-tools";

export const maxDuration = 30;

export async function POST(req: Request) {
  const { messages }: { messages: UIMessage[] } = await req.json();

  const result = streamText({
    model: google("gemini-3.6-flash"),
    system:
      "You are a financial research assistant. Use tools to get real quotes, news, and price history before answering. Cite sources.",
    messages: await convertToModelMessages(messages),
    tools: { getQuote, getNews, getHistoricalPrices },
  });

  return createUIMessageStreamResponse({
    stream: toUIMessageStream({
      stream: result.stream,
      onError: (error) => {
        console.error(error);
        if (error instanceof Error) return error.message;
        return "An error occurred.";
      },
    }),
  });
}
