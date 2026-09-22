import { z } from "zod";

export const QuoteSchema = z.object({
  symbol: z.string(),
  price: z.number(),
  changePercent: z.number(),
  volume: z.number(),
  asOf: z.string(),
});

export const NewsItemSchema = z.object({
  headline: z.string(),
  summary: z.string(),
  url: z.string().url(),
  publishedAt: z.string(),
});

export const HistoricalPriceSchema = z.object({
  time: z.string(), // "2026-09-21"
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
  volume: z.number(),
});

export type Quote = z.infer<typeof QuoteSchema>;
export type NewsItem = z.infer<typeof NewsItemSchema>;
export type HistoricalPrice = z.infer<typeof HistoricalPriceSchema>;
