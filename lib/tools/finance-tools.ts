import { tool } from "ai";
import { z } from "zod";
import { alphaVantageRequest, parseAlphaVantageTimestamp } from "../alpha-vantage";
import {
  QuoteSchema,
  NewsItemSchema,
  HistoricalPriceSchema,
} from "../schemas/finance";

export const getQuote = tool({
  description: "Get the latest price and daily change for a US equity ticker",
  inputSchema: z.object({ symbol: z.string().describe("Ticker, e.g. NVDA") }),
  execute: async ({ symbol }) => {
    const data = await alphaVantageRequest({
      function: "GLOBAL_QUOTE",
      symbol,
    });
    const quote = data["Global Quote"] as Record<string, string> | undefined;
    if (!quote || !quote["05. price"]) {
      throw new Error(`No quote data found for ${symbol}`);
    }

    return QuoteSchema.parse({
      symbol,
      price: Number(quote["05. price"]),
      changePercent: Number(quote["10. change percent"].replace("%", "")),
      volume: Number(quote["06. volume"]),
      asOf: new Date(
        `${quote["07. latest trading day"]}T00:00:00Z`,
      ).toISOString(),
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
    const data = await alphaVantageRequest({
      function: "NEWS_SENTIMENT",
      tickers: symbol,
      limit: String(limit),
    });
    const feed = data["feed"] as Array<Record<string, string>> | undefined;
    if (!feed) {
      return { items: [] as z.infer<typeof NewsItemSchema>[] };
    }

    const items = feed.slice(0, limit).map((item) =>
      NewsItemSchema.parse({
        headline: item.title,
        summary: item.summary,
        url: item.url,
        publishedAt: parseAlphaVantageTimestamp(item.time_published),
      }),
    );

    return { items };
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
    const data = await alphaVantageRequest({
      function: "TIME_SERIES_DAILY",
      symbol,
      outputsize: days > 100 ? "full" : "compact",
    });
    const series = data["Time Series (Daily)"] as
      | Record<string, Record<string, string>>
      | undefined;
    if (!series) {
      throw new Error(`No historical data found for ${symbol}`);
    }

    const candles = Object.entries(series)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-days)
      .map(([time, values]) =>
        HistoricalPriceSchema.parse({
          time,
          open: Number(values["1. open"]),
          high: Number(values["2. high"]),
          low: Number(values["3. low"]),
          close: Number(values["4. close"]),
          volume: Number(values["5. volume"]),
        }),
      );

    return { candles };
  },
});
