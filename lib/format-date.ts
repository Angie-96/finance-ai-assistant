// Single display format for dates across the UI, e.g. "Sep 23, 2026".
// Market dates are trading days stored at UTC midnight (or as "YYYY-MM-DD",
// which Date also parses as UTC), so format in UTC to avoid local time zones
// rolling them back a day. The chat system prompt asks the model for this
// same format — keep them in sync.
const formatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeZone: "UTC",
});

export function formatDate(value: string | Date): string {
  return formatter.format(typeof value === "string" ? new Date(value) : value);
}
