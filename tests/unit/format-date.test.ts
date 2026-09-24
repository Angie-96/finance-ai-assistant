import { describe, expect, it } from "vitest";
import { formatDate } from "@/lib/format-date";

describe("formatDate", () => {
  it("formats ISO timestamps and YYYY-MM-DD strings the same way", () => {
    expect(formatDate("2026-09-23T00:00:00.000Z")).toBe("Sep 23, 2026");
    expect(formatDate("2026-09-23")).toBe("Sep 23, 2026");
  });

  it("formats in UTC so a trading day at UTC midnight isn't shifted", () => {
    expect(formatDate(new Date(Date.UTC(2026, 0, 1)))).toBe("Jan 1, 2026");
  });
});
