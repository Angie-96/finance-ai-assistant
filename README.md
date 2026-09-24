# Finance AI Assistant

A chat app for financial research questions. Instead of guessing at numbers, the model calls tools that fetch real market data from [Alpha Vantage](https://www.alphavantage.co/): live quotes, recent news, and daily price history (drawn as a candlestick chart).

Ask things like:

- "What's NVDA trading at today?"
- "Show me the last 60 days of AAPL."
- "Any recent news on TSLA?"

## Tech stack

- [Next.js 16](https://nextjs.org) (App Router), React 19, TypeScript
- [Vercel AI SDK](https://ai-sdk.dev) with Google Gemini (`gemini-3.6-flash`) for streaming chat and tool calling
- [Alpha Vantage](https://www.alphavantage.co/documentation/) for market data
- [Zod](https://zod.dev) to validate API responses
- [lightweight-charts](https://github.com/tradingview/lightweight-charts) and [Recharts](https://recharts.org) for charts
- Tailwind CSS v4
- Vitest and Testing Library (unit tests), Playwright with axe-core (e2e and accessibility tests)

## Getting started

### Prerequisites

- Node.js 24 (see `.nvmrc`; run `nvm use` if you use nvm)
- An [Alpha Vantage API key](https://www.alphavantage.co/support/#api-key) (free)
- A [Google AI Studio API key](https://aistudio.google.com/app/apikey) for Gemini (free tier available)

### Setup

```bash
git clone git@github.com:Angie-96/finance-ai-assistant.git
cd finance-ai-assistant
npm install
```

Create a `.env.local` file in the project root:

```bash
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
GOOGLE_GENERATIVE_AI_API_KEY=your_gemini_key
```

Start the dev server:

```bash
npm run dev
```

Then open [http://localhost:3000](http://localhost:3000).

## Scripts

| Command | What it does |
| --- | --- |
| `npm run dev` | Start the dev server |
| `npm run build` | Create a production build |
| `npm run start` | Serve the production build |
| `npm run lint` | Run ESLint |
| `npx tsc --noEmit` | Type-check the project (run `npx next typegen` first) |
| `npm run test` | Run the Vitest unit tests |
| `npm run test:e2e` | Run the Playwright end-to-end tests (needs both API keys) |

## How it works

```
Browser (Chat UI)
   │  POST /api/chat
   ▼
app/api/chat/route.ts ── streamText (Gemini) ──▶ picks and calls tools
   │
   ▼
lib/tools/finance-tools.ts   getQuote · getNews · getHistoricalPrices
   │
   ▼
lib/alpha-vantage.ts          cache (5 min) + throttle (1 request per 1.5 s)
   │
   ▼
Alpha Vantage REST API
```

- **`app/api/chat/route.ts`** streams the model's reply. The system prompt tells the model to look up real data with its tools before answering, and to cite sources.
- **`lib/tools/finance-tools.ts`** defines the three tools. Each one calls Alpha Vantage and checks the result against a Zod schema from `lib/schemas/finance.ts`.
- **`lib/alpha-vantage.ts`** is the only code that talks to Alpha Vantage:
  - **Caching:** responses are kept in memory for 5 minutes, keyed by request URL.
  - **Throttling:** requests run one at a time, at least 1.5 seconds apart. The free tier allows 1 request per second, and the model often calls several tools in one turn.
- **`components/`** holds the UI: the chat (`chat/Chat.tsx`), the candlestick chart with hover tooltips (`chart/CandlestickChart.tsx`), and the light/dark theme toggle (`theme/ThemeToggle.tsx`).

### Adding a tool

1. Add a Zod schema for the tool's output in `lib/schemas/finance.ts`.
2. Define the tool in `lib/tools/finance-tools.ts`. Call Alpha Vantage through `alphaVantageRequest` (never `fetch` directly), so caching and throttling still apply.
3. Register the tool in the `tools` object in `app/api/chat/route.ts`.
4. Add a unit test in `tests/unit/`. If the tool changes the UI, add a Playwright test in `tests/e2e/` too.

## Testing

- **Unit tests** (`tests/unit/`) use Vitest, jsdom, and Testing Library.
- **End-to-end tests** (`tests/e2e/`) use Playwright, with axe-core checking accessibility. They hit the real APIs, so both keys must be set.

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and pull request to `main`. It runs lint, typegen, typecheck, unit tests, the production build, and the Playwright e2e tests. For the e2e step to work, add `ALPHA_VANTAGE_API_KEY` and `GOOGLE_GENERATIVE_AI_API_KEY` as repository secrets.

If you use Claude Code, the `/check` command runs the same checks locally, except e2e.

## Limitations

- **Rate limits:** Alpha Vantage's free tier is limited to about 25 requests per day, and 1 per second. The cache and throttle help, but a busy session can still run out.
- **US stocks only:** the tools are written for US equity tickers.
- **Not financial advice:** this is a research demo. The model can still misread or misstate data.
