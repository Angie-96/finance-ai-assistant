"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import { useState } from "react";
import type { Quote, NewsItem, HistoricalPrice } from "@/lib/schemas/finance";

const SUGGESTIONS = [
  "What's the latest quote for NVDA?",
  "Any recent news on AAPL?",
  "Show me TSLA's price history over the last 30 days",
];

export function Chat() {
  const { messages, sendMessage, status, error, regenerate } = useChat({
    transport: new DefaultChatTransport({ api: "/api/chat" }),
  });
  const [input, setInput] = useState("");

  const isBusy = status === "submitted" || status === "streaming";

  const submit = (text: string) => {
    if (!text.trim() || isBusy) return;
    sendMessage({ text });
    setInput("");
  };

  return (
    <div className="flex h-dvh w-full flex-col">
      <header className="border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
          Finance Research Assistant
        </h1>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Ask about quotes, news, or price history for US equities.
        </p>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {messages.length === 0 ? (
          <div className="mx-auto flex max-w-md flex-col gap-2 pt-12 text-center">
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Try asking:
            </p>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => submit(s)}
                className="rounded-lg border border-zinc-200 px-4 py-2 text-left text-sm text-zinc-700 transition-colors hover:bg-zinc-50 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-900"
              >
                {s}
              </button>
            ))}
          </div>
        ) : (
          <div className="mx-auto flex max-w-2xl flex-col gap-6">
            {messages.map((message) => (
              <div key={message.id} className="flex flex-col gap-2">
                <span className="text-xs font-medium uppercase tracking-wide text-zinc-400">
                  {message.role === "user" ? "You" : "Assistant"}
                </span>
                <div className="flex flex-col gap-3">
                  {message.parts.map((part, index) => (
                    <MessagePart key={index} part={part} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {error && (
          <div className="mx-auto mt-4 flex max-w-2xl flex-col gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
            <span>Something went wrong.</span>
            <button
              type="button"
              onClick={() => regenerate()}
              className="self-start font-medium underline"
            >
              Retry
            </button>
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
        className="mx-auto flex w-full max-w-2xl gap-2 border-t border-zinc-200 px-6 py-4 dark:border-zinc-800"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={isBusy}
          placeholder="Ask about a stock..."
          className="flex-1 rounded-full border border-zinc-200 bg-white px-4 py-2 text-sm text-zinc-900 outline-none focus:border-zinc-400 disabled:opacity-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-50"
        />
        <button
          type="submit"
          disabled={isBusy || !input.trim()}
          className="rounded-full bg-zinc-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-zinc-50 dark:text-zinc-900"
        >
          {isBusy ? "..." : "Send"}
        </button>
      </form>
    </div>
  );
}

type UIMessagePart = ReturnType<typeof useChat>["messages"][number]["parts"][number];

function MessagePart({ part }: { part: UIMessagePart }) {
  switch (part.type) {
    case "text":
      return (
        <p className="whitespace-pre-wrap text-sm text-zinc-800 dark:text-zinc-200">
          {part.text}
        </p>
      );

    case "tool-getQuote":
      switch (part.state) {
        case "input-streaming":
        case "input-available":
          return (
            <ToolStatus
              label={`Fetching quote for ${(part.input as { symbol?: string } | undefined)?.symbol ?? "..."}`}
            />
          );
        case "output-available":
          return <QuoteCard quote={part.output as Quote} />;
        case "output-error":
          return <ToolError message={part.errorText} />;
        default:
          return null;
      }

    case "tool-getNews":
      switch (part.state) {
        case "input-streaming":
        case "input-available":
          return (
            <ToolStatus
              label={`Looking up news for ${(part.input as { symbol?: string } | undefined)?.symbol ?? "..."}`}
            />
          );
        case "output-available": {
          const items = (part.output as { items: NewsItem[] })?.items ?? [];
          return <NewsList items={items} />;
        }
        case "output-error":
          return <ToolError message={part.errorText} />;
        default:
          return null;
      }

    case "tool-getHistoricalPrices":
      switch (part.state) {
        case "input-streaming":
        case "input-available":
          return (
            <ToolStatus
              label={`Pulling price history for ${(part.input as { symbol?: string } | undefined)?.symbol ?? "..."}`}
            />
          );
        case "output-available": {
          const candles =
            (part.output as { candles: HistoricalPrice[] })?.candles ?? [];
          return <PriceHistoryTable candles={candles} />;
        }
        case "output-error":
          return <ToolError message={part.errorText} />;
        default:
          return null;
      }

    case "step-start":
      return null;

    default:
      return null;
  }
}

function ToolStatus({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-zinc-400" />
      {label}
    </div>
  );
}

function ToolError({ message }: { message?: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
      {message ?? "Tool call failed."}
    </div>
  );
}

function QuoteCard({ quote }: { quote: Quote }) {
  const isUp = quote.changePercent >= 0;
  return (
    <div className="flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-3 dark:border-zinc-800">
      <div>
        <p className="font-mono text-sm font-semibold text-zinc-900 dark:text-zinc-50">
          {quote.symbol}
        </p>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          as of {new Date(quote.asOf).toLocaleString()}
        </p>
      </div>
      <div className="text-right">
        <p className="font-mono text-sm text-zinc-900 dark:text-zinc-50">
          ${quote.price.toFixed(2)}
        </p>
        <p
          className={`text-xs font-medium ${isUp ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}
        >
          {isUp ? "+" : ""}
          {quote.changePercent.toFixed(2)}%
        </p>
      </div>
    </div>
  );
}

function NewsList({ items }: { items: NewsItem[] }) {
  if (items.length === 0) {
    return (
      <p className="text-xs text-zinc-500 dark:text-zinc-400">
        No recent news found.
      </p>
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {items.map((item) => (
        <li
          key={item.url}
          className="rounded-lg border border-zinc-200 px-4 py-3 dark:border-zinc-800"
        >
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-zinc-900 hover:underline dark:text-zinc-50"
          >
            {item.headline}
          </a>
          <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
            {item.summary}
          </p>
        </li>
      ))}
    </ul>
  );
}

function PriceHistoryTable({ candles }: { candles: HistoricalPrice[] }) {
  if (candles.length === 0) {
    return (
      <p className="text-xs text-zinc-500 dark:text-zinc-400">
        No historical data found.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full text-left text-xs">
        <thead className="border-b border-zinc-200 text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
          <tr>
            <th className="px-3 py-2">Date</th>
            <th className="px-3 py-2">Open</th>
            <th className="px-3 py-2">High</th>
            <th className="px-3 py-2">Low</th>
            <th className="px-3 py-2">Close</th>
          </tr>
        </thead>
        <tbody>
          {candles.slice(-10).map((c) => (
            <tr key={c.time} className="border-b border-zinc-100 last:border-0 dark:border-zinc-900">
              <td className="px-3 py-2 font-mono">{c.time}</td>
              <td className="px-3 py-2 font-mono">{c.open.toFixed(2)}</td>
              <td className="px-3 py-2 font-mono">{c.high.toFixed(2)}</td>
              <td className="px-3 py-2 font-mono">{c.low.toFixed(2)}</td>
              <td className="px-3 py-2 font-mono">{c.close.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
