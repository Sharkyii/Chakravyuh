import { test, expect } from "@playwright/test";

// Fails the test if the page logs a console error at any point during it --
// this is what actually caught the two real bugs found manually this
// session (invisible SVG path edges, an undefined ref) that a plain
// "does it render" check would have missed.
function trackConsoleErrors(page: import("@playwright/test").Page) {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
  return errors;
}

test("boot sequence completes with no credentials and no console errors", async ({ page }) => {
  const errors = trackConsoleErrors(page);
  await page.goto("/");
  await expect(page.getByText("CHAKRAVYUH")).toBeVisible();
  // The boot animation replaced the login form -- there must be no
  // username/password fields to fill in.
  await expect(page.locator('input[type="password"]')).toHaveCount(0);

  await expect(page.getByText("access granted.")).toBeVisible({ timeout: 8000 });
  await expect(page.getByText("Risk Scoring Studio")).toBeVisible({ timeout: 3000 });
  expect(errors).toEqual([]);
});

test("scenario picker loads from the live API", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Risk Scoring Studio")).toBeVisible({ timeout: 8000 });
  // Options inside a native <select> report as "hidden" to Playwright's
  // visibility check even when rendered, so assert on the select instead.
  const scenarioSelect = page.locator("select").first();
  await expect(scenarioSelect).toBeVisible({ timeout: 5000 });
  await expect(
    scenarioSelect.locator("option", { hasText: "Standard Genuine Payment" })
  ).toHaveCount(1);
});

test("attack connection graph tab renders without console errors", async ({ page }) => {
  const errors = trackConsoleErrors(page);
  await page.goto("/");
  await expect(page.getByText("Risk Scoring Studio")).toBeVisible({ timeout: 8000 });

  await page.getByRole("button", { name: "Attack Connection Graph" }).click();
  await expect(page.getByText("NETWORK CONNECTION GRAPH")).toBeVisible();
  // At least one node from the 13-generator catalogue should render.
  // Scoped to the svg since the same label also appears in the side detail
  // panel's heading -- an unscoped locator matches both and fails strict mode.
  await expect(page.locator("svg").getByText("Credential Takeover")).toBeVisible();
  await page.waitForTimeout(500); // let SVG path draws settle
  expect(errors).toEqual([]);
});

test("closed-loop intelligence tab renders without console errors", async ({ page }) => {
  const errors = trackConsoleErrors(page);
  await page.goto("/");
  await expect(page.getByText("Risk Scoring Studio")).toBeVisible({ timeout: 8000 });

  await page.getByRole("button", { name: "Closed-Loop Intelligence" }).click();
  await page.waitForTimeout(500);
  expect(errors).toEqual([]);
});

test("risk assessment run either scores the transaction or fails gracefully", async ({ page }) => {
  // Does not assume a trained model is present (CI doesn't train one) --
  // both outcomes below are "not broken." What must never happen is an
  // unhandled exception or a blank screen.
  const errors = trackConsoleErrors(page);
  await page.goto("/");
  await expect(page.getByText("Risk Scoring Studio")).toBeVisible({ timeout: 8000 });

  await page.getByRole("button", { name: /Run Risk Assessment/i }).click();

  // Matches whatever error text the backend actually returns (e.g. a 404
  // when CI hasn't trained models) rather than a specific guessed message.
  const resultVisible = page.getByText("TOP PREDICTED ATTACK VECTOR");
  const errorVisible = page.getByTestId("score-error");
  await expect(resultVisible.or(errorVisible)).toBeVisible({ timeout: 10000 });
  const filteredErrors = errors.filter(e => !e.includes("Failed to load resource"));
  expect(filteredErrors).toEqual([]);
});
