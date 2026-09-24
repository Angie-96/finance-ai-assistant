"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import { useState, type ReactNode } from "react";
import { AnimatePresence, MotionConfig, motion } from "motion/react";
import type { Quote, NewsItem, HistoricalPrice } from "@/lib/schemas/finance";
import { CandlestickChart } from "@/components/chart/CandlestickChart";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { Markdown } from "@/components/chat/Markdown";
import { formatDate } from "@/lib/format-date";
import {
  blurSwap,
  exitTransition,
  riseIn,
  staggerChildren,
} from "@/components/motion/transitions";

const SUGGESTIONS = [
  "What's the latest quote for NVDA?",
  "Any recent news on AAPL?",
  "Show me TSLA's price history over the last 30 days",
];

export function Chat() {
  // Set when a reply ends without the model finishing normally (e.g. Gemini
  // returns finishReason "other" mid-answer), so a truncated reply isn't
  // presented as complete.
  const [cutOff, setCutOff] = useState(false);
  const { messages, sendMessage, status, error, regenerate } = useChat({
    transport: new DefaultChatTransport({ api: "/api/chat" }),
    onFinish: ({ finishReason, isAbort, isDisconnect, isError }) => {
      if (isError || isAbort) return;
      setCutOff(isDisconnect || (finishReason !== undefined && finishReason !== "stop"));
    },
  });
  const [input, setInput] = useState("");

  const isBusy = status === "submitted" || status === "streaming";

  const submit = (text: string) => {
    if (!text.trim() || isBusy) return;
    setCutOff(false);
    sendMessage({ text });
    setInput("");
  };

  const retry = () => {
    setCutOff(false);
    regenerate();
  };

  return (
    // reducedMotion="user": honor the OS setting by dropping transform-based
    // movement while keeping opacity fades.
    <MotionConfig reducedMotion="user">
      <div className="flex h-dvh w-full flex-col">
        <header className="flex items-start justify-between border-b border-zinc-200 px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-4 sm:px-6 dark:border-zinc-800">
          <div>
            <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
              Finance Research Assistant
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Ask about quotes, news, or price history for US equities.
            </p>
          </div>
          <ThemeToggle />
        </header>

        <main className="flex flex-1 min-h-0 flex-col">
          <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-6">
            {messages.length === 0 ? (
              <motion.div
                variants={staggerChildren(0.05)}
                initial="hidden"
                animate="visible"
                className="mx-auto flex max-w-md flex-col gap-2 pt-8 text-center sm:pt-12"
              >
                <motion.p
                  variants={riseIn}
                  className="text-sm text-zinc-500 dark:text-zinc-400"
                >
                  Try asking:
                </motion.p>
                {SUGGESTIONS.map((s) => (
                  <motion.button
                    key={s}
                    type="button"
                    variants={riseIn}
                    whileTap={{ scale: 0.97 }}
                    onClick={() => submit(s)}
                    className="rounded-lg border border-zinc-200 px-4 py-3 text-left text-sm text-zinc-700 transition-colors hover:bg-zinc-50 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-900"
                  >
                    {s}
                  </motion.button>
                ))}
              </motion.div>
            ) : (
              // TODO: add role="log"/aria-live="polite" so screen readers announce streamed messages
              <div className="mx-auto flex max-w-2xl flex-col gap-6">
                {messages.map((message) => (
                  <motion.div
                    key={message.id}
                    variants={riseIn}
                    initial="hidden"
                    animate="visible"
                    className="flex flex-col gap-2"
                  >
                    <span className="text-xs font-medium uppercase tracking-wide text-zinc-400">
                      {message.role === "user" ? "You" : "Assistant"}
                    </span>
                    <div className="flex flex-col gap-3">
                      {message.parts.map((part, index) => (
                        <MessagePart
                          key={index}
                          part={part}
                          role={message.role}
                        />
                      ))}
                    </div>
                  </motion.div>
                ))}

                {status === "submitted" && (
                  <motion.div
                    variants={riseIn}
                    initial="hidden"
                    animate="visible"
                    className="flex flex-col gap-2"
                  >
                    <span className="text-xs font-medium uppercase tracking-wide text-zinc-400">
                      Assistant
                    </span>
                    <TypingIndicator />
                  </motion.div>
                )}
              </div>
            )}

            <AnimatePresence>
              {error ? (
                <Notice key="error" tone="error" onRetry={retry}>
                  {isQuotaError(error)
                    ? "The AI model's free-tier limit was reached. Wait a minute and retry — if it keeps happening, the daily limit is used up."
                    : "Something went wrong."}
                </Notice>
              ) : (
                cutOff &&
                !isBusy && (
                  <Notice key="cut-off" tone="warning" onRetry={retry}>
                    This reply was cut off before it finished.
                  </Notice>
                )
              )}
            </AnimatePresence>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              submit(input);
            }}
            className="mx-auto flex w-full max-w-2xl gap-2 border-t border-zinc-200 px-4 pt-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] sm:px-6 sm:pt-4 dark:border-zinc-800"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isBusy}
              placeholder="Ask about a stock..."
              className="flex-1 rounded-full border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-900 outline-none focus:border-zinc-400 disabled:opacity-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-50"
            />
            <button
              type="submit"
              disabled={isBusy || !input.trim()}
              className="relative flex min-w-[4.5rem] items-center justify-center rounded-full bg-zinc-900 px-5 py-3 text-sm font-medium text-white transition-transform active:scale-[0.97] disabled:opacity-40 dark:bg-zinc-50 dark:text-zinc-900"
            >
              <AnimatePresence mode="popLayout" initial={false}>
                <motion.span
                  key={isBusy ? "busy" : "idle"}
                  variants={blurSwap}
                  initial="hidden"
                  animate="visible"
                  exit="exit"
                  className="flex items-center justify-center"
                >
                  {isBusy ? <Spinner /> : "Send"}
                </motion.span>
              </AnimatePresence>
            </button>
          </form>
        </main>
      </div>
    </MotionConfig>
  );
}

function isQuotaError(error: Error): boolean {
  return /quota|rate limit|resource.?exhausted/i.test(error.message);
}

function Notice({
  tone,
  onRetry,
  children,
}: {
  tone: "error" | "warning";
  onRetry: () => void;
  children: ReactNode;
}) {
  const toneClass =
    tone === "error"
      ? "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300"
      : "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300";
  return (
    <motion.div
      role="status"
      variants={riseIn}
      initial="hidden"
      animate="visible"
      exit={{ opacity: 0, transition: exitTransition }}
      className={`mx-auto mt-4 flex max-w-2xl flex-col gap-2 rounded-lg border px-4 py-3 text-sm ${toneClass}`}
    >
      <span>{children}</span>
      <button
        type="button"
        onClick={onRetry}
        className="self-start font-medium underline"
      >
        Retry
      </button>
    </motion.div>
  );
}

type UIMessage = ReturnType<typeof useChat>["messages"][number];
type UIMessagePart = UIMessage["parts"][number];

function MessagePart({
  part,
  role,
}: {
  part: UIMessagePart;
  role: UIMessage["role"];
}) {
  const content = renderPart(part, role);
  if (content === null) return null;

  if (part.type.startsWith("tool-") && "state" in part) {
    // Both input states render the same loading line, so treat them as one
    // phase; otherwise the line would re-animate as the input finishes streaming.
    const phase =
      part.state === "input-streaming" || part.state === "input-available"
        ? "loading"
        : (part.state ?? "loading");
    return <ToolPhaseSwap phase={phase}>{content}</ToolPhaseSwap>;
  }

  return content;
}

function ToolPhaseSwap({
  phase,
  children,
}: {
  phase: string;
  children: ReactNode;
}) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={phase}
        variants={blurSwap}
        initial="hidden"
        animate="visible"
        exit="exit"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

function renderPart(part: UIMessagePart, role: UIMessage["role"]): ReactNode {
  switch (part.type) {
    case "text":
      // Assistant replies are markdown; user input is shown exactly as typed.
      if (role === "assistant") return <Markdown>{part.text}</Markdown>;
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
          return <CandlestickChart candles={candles} />;
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

function Spinner() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      className="h-4 w-4 animate-spin"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4Z"
      />
    </svg>
  );
}

function TypingIndicator() {
  return (
    <div
      role="status"
      aria-label="Assistant is typing"
      className="flex items-center gap-1 px-1 py-2"
    >
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-400 motion-reduce:animate-none [animation-delay:-0.3s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-400 motion-reduce:animate-none [animation-delay:-0.15s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-400 motion-reduce:animate-none" />
    </div>
  );
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
    <div className="flex flex-col gap-2 rounded-lg border border-zinc-200 px-4 py-3 sm:flex-row sm:items-center sm:justify-between dark:border-zinc-800">
      <div>
        <p className="font-mono text-sm font-semibold text-zinc-900 dark:text-zinc-50">
          {quote.symbol}
        </p>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          as of {formatDate(quote.asOf)}
        </p>
      </div>
      <div className="sm:text-right">
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

function ExternalLinkIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-3.5 w-3.5"
      aria-hidden="true"
    >
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <path d="M15 3h6v6" />
      <path d="M10 14 21 3" />
    </svg>
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
    <motion.ul
      variants={staggerChildren()}
      initial="hidden"
      animate="visible"
      className="flex flex-col gap-2"
    >
      {items.map((item) => (
        <motion.li
          key={item.url}
          variants={riseIn}
          className="flex items-start justify-between gap-3 rounded-lg border border-zinc-200 px-4 py-3 dark:border-zinc-800"
        >
          <div>
            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
              {item.headline}
            </p>
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
              {item.summary}
            </p>
          </div>
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Open article: ${item.headline}`}
            className="flex shrink-0 items-center gap-1 rounded-full border border-zinc-200 px-3 py-2 text-xs font-medium text-zinc-700 transition-transform hover:bg-zinc-50 active:scale-[0.97] dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            Open
            <ExternalLinkIcon />
          </a>
        </motion.li>
      ))}
    </motion.ul>
  );
}
