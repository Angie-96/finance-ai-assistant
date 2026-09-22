import { tool } from "ai";
import { z } from "zod";
import {
  QuoteSchema,
  NewsItemSchema,
  HistoricalPriceSchema,
} from "../schemas/finance";

export const getQuote = tool({
  description: "Get the latest price and daily change for a US equity ticker",
  inputSchema: z.object({ symbol: z.string().describe("Ticker, e.g. NVDA") }),
  execute: async ({ symbol }) => {
    // TODO: replace with real Alpha Vantage call
    return QuoteSchema.parse({
      symbol,
      price: 0,
      changePercent: 0,
      volume: 0,
      asOf: new Date().toISOString(),
    });
  },
});

export const getNews = tool({
  description: "Get recent news headlines for a US equity ticker",
  inputSchema: z.object({
    symbol: z.string(),
    limit: z.number().default(5),
  }),
  execute: async ({ symbol, limit }) => {
    // TODO: replace with real news API call
    return { items: [] as z.infer<typeof NewsItemSchema>[] };
  },
});

export const getHistoricalPrices = tool({
  description:
    "Get daily OHLCV candles for a US equity ticker over a date range",
  inputSchema: z.object({
    symbol: z.string(),
    days: z.number().default(30),
  }),
  execute: async ({ symbol, days }) => {
    // TODO: replace with real historical data call
    let price = 100 + (symbol.charCodeAt(0) % 20) * 5;
    const candles: z.infer<typeof HistoricalPriceSchema>[] = [];
    const today = new Date();

    for (let i = days; i > 0; i--) {
      const date = new Date(today);
      date.setDate(date.getDate() - i);

      const open = price;
      const drift = (Math.sin(i / 3) + Math.random() - 0.5) * 3;
      const close = Math.max(1, open + drift);
      const high = Math.max(open, close) + Math.random() * 2;
      const low = Math.min(open, close) - Math.random() * 2;

      candles.push({
        time: date.toISOString().slice(0, 10),
        open: Number(open.toFixed(2)),
        high: Number(high.toFixed(2)),
        low: Number(low.toFixed(2)),
        close: Number(close.toFixed(2)),
        volume: Math.floor(1_000_000 + Math.random() * 5_000_000),
      });

      price = close;
    }

    return { candles };
  },
});
