const BASE_URL = "https://www.alphavantage.co/query";
const CACHE_TTL_MS = 5 * 60 * 1000;
const MIN_REQUEST_INTERVAL_MS = 1500;

export class AlphaVantageError extends Error {}

const cache = new Map<string, { data: Record<string, unknown>; expiresAt: number }>();

// Alpha Vantage's free tier allows only 1 request/second. The model can call
// multiple tools in the same turn (e.g. getQuote + getHistoricalPrices), so
// requests must be serialized here rather than fired concurrently.
let requestQueue: Promise<void> = Promise.resolve();
let lastRequestAt = 0;

function throttle(): Promise<void> {
  const next = requestQueue.then(async () => {
    const wait = Math.max(0, lastRequestAt + MIN_REQUEST_INTERVAL_MS - Date.now());
    if (wait > 0) {
      await new Promise((resolve) => setTimeout(resolve, wait));
    }
    lastRequestAt = Date.now();
  });
  requestQueue = next;
  return next;
}

export async function alphaVantageRequest(
  params: Record<string, string>,
): Promise<Record<string, unknown>> {
  const apiKey = process.env.ALPHA_VANTAGE_API_KEY;
  if (!apiKey) {
    throw new AlphaVantageError("ALPHA_VANTAGE_API_KEY is not set");
  }

  const url = new URL(BASE_URL);
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value);
  }
  const cacheKey = url.toString();

  const cached = cache.get(cacheKey);
  if (cached && cached.expiresAt > Date.now()) {
    return cached.data;
  }

  url.searchParams.set("apikey", apiKey);

  await throttle();
  const response = await fetch(url);
  if (!response.ok) {
    throw new AlphaVantageError(
      `Alpha Vantage request failed with status ${response.status}`,
    );
  }

  const data = (await response.json()) as Record<string, unknown>;

  const errorMessage =
    data["Error Message"] ?? data["Note"] ?? data["Information"];
  if (typeof errorMessage === "string") {
    throw new AlphaVantageError(errorMessage);
  }

  cache.set(cacheKey, { data, expiresAt: Date.now() + CACHE_TTL_MS });

  return data;
}

export function parseAlphaVantageTimestamp(raw: string): string {
  const match = raw.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})$/);
  if (!match) {
    throw new AlphaVantageError(`Unrecognized timestamp format: ${raw}`);
  }
  const [, year, month, day, hour, minute, second] = match;
  return new Date(
    Date.UTC(
      Number(year),
      Number(month) - 1,
      Number(day),
      Number(hour),
      Number(minute),
      Number(second),
    ),
  ).toISOString();
}
