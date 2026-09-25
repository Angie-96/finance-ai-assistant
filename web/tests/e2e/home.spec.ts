import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("home page renders the chat and has no accessibility violations", async ({
  page,
}) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: /finance research assistant/i }),
  ).toBeVisible();

  // Suggestions fade in with a stagger; axe would flag contrast mid-fade.
  await expect(
    page.getByRole("button", { name: /price history over the last 30 days/i }),
  ).toHaveCSS("opacity", "1");

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
