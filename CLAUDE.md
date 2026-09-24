@AGENTS.md

# Finance AI Assistant

A Next.js 16 chat app that answers financial research questions using tool-calling. The model (Gemini, via AI SDK) calls tools backed by Alpha Vantage to get real quotes/news/prices instead of hallucinating them.

## Stack
- Next.js 16 (App Router) + React 19 + TypeScript
- AI: `ai` (Vercel AI SDK) + `@ai-sdk/google` (Gemini) — **not Anthropic**. Switched from Claude to Gemini early on for the free tier; keep using Gemini unless the user asks to switch back.
- Charts: `lightweight-charts` (candlesticks) and `recharts`
- Data: Alpha Vantage REST API (free tier: 1 req/sec)
- Testing: Vitest (unit) + Playwright (e2e, incl. `@axe-core/playwright` for a11y)

## Environment
Required in `.env.local` (see `.env.local` for actual values, never print/log them):
- `ALPHA_VANTAGE_API_KEY`
- `GOOGLE_GENERATIVE_AI_API_KEY`

## Commands
- `npm run dev` — dev server
- `npm run lint` — ESLint
- `npx tsc --noEmit` — typecheck (CI also runs `npx next typegen` first)
- `npm run test` — Vitest unit tests
- `npm run test:e2e` — Playwright e2e
- `npm run build` — production build
- `/check` (Claude Code command) — runs lint + typegen + typecheck + unit tests + build, mirroring CI, before you push

## Architecture
- `app/api/chat/route.ts` — chat endpoint; streams `streamText` output using the Gemini model and the finance tools below.
- `lib/tools/finance-tools.ts` — AI SDK `tool()` definitions: `getQuote`, `getNews`, `getHistoricalPrices`. Each calls `alphaVantageRequest` and parses the response through a Zod schema from `lib/schemas/finance.ts`.
- `lib/alpha-vantage.ts` — the only place that talks to Alpha Vantage. Handles:
  - **Caching**: in-memory `Map`, 5 min TTL, keyed by full request URL.
  - **Throttling**: requests are serialized through a promise chain with a 1.5s minimum interval, because the model can call multiple tools in one turn and Alpha Vantage's free tier allows only 1 req/sec. Do not bypass this by calling `fetch` directly elsewhere — always go through `alphaVantageRequest`.
- `lib/schemas/finance.ts` — Zod schemas (`QuoteSchema`, `NewsItemSchema`, `HistoricalPriceSchema`) that double as TS types via `z.infer`.
- `components/chat/Chat.tsx`, `components/chart/CandlestickChart.tsx`, `components/theme/ThemeToggle.tsx` — UI.

## Adding a new finance tool
Follow the existing pattern rather than inventing a new one:
1. Add a Zod schema for the tool's return shape in `lib/schemas/finance.ts`.
2. Add the Alpha Vantage call in `lib/tools/finance-tools.ts` using `alphaVantageRequest` (gets caching/throttling for free) and parse the result through the schema.
3. Register the tool in the `tools: {}` object in `app/api/chat/route.ts`.
4. Add a unit test and, if it affects the UI, a Playwright check.

## Testing conventions
- Unit tests live in `tests/unit/`, e2e in `tests/e2e/`.
- For any UI/frontend change, start the dev server and exercise it in a real browser (chat flow, chart rendering/tooltips, theme toggle) before calling the task done — Vitest/type checks verify correctness, not that the feature actually works.

## CI
`.github/workflows/ci.yml` runs lint, typegen, typecheck, unit tests, and build on every push/PR to `main`. Playwright e2e is **not** wired into CI yet — it needs `ALPHA_VANTAGE_API_KEY`/`GOOGLE_GENERATIVE_AI_API_KEY` as repo secrets first.
