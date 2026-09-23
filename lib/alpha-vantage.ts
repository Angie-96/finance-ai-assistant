const BASE_URL = "https://www.alphavantage.co/query";

export class AlphaVantageError extends Error {}

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
  url.searchParams.set("apikey", apiKey);

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

  return data;
}
