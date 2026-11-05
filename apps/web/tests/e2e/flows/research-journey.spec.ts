import { test, expect } from "../fixtures/test";
import { captureQaScreenshot } from "../fixtures/screenshots";

test("a new visitor can research, replay, save and reopen a perspective", async ({
  page,
  pageErrors,
}) => {
  const initialStocks = page.waitForResponse(
    (response) => new URL(response.url()).pathname === "/api/stocks",
  );
  await page.goto("/");
  await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toBeVisible();
  expect((await initialStocks).fromServiceWorker()).toBe(true);
  await expect(
    page.getByRole("main").getByText("Apple Inc.", { exact: true }).first(),
  ).toBeVisible();
  await captureQaScreenshot(page, "desktop-home");

  await page.getByRole("button", { name: "Search stocks", exact: true }).click();
  const search = page.getByRole("dialog");
  await search.getByRole("textbox", { name: "Search company or ticker" }).fill("AAPL");
  await expect(search.getByRole("link")).toHaveCount(1);
  await search.getByRole("link").filter({ hasText: "AAPL" }).click();
  await expect(page).toHaveURL(/\/stocks\/AAPL$/);
  await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toContainText(/Apple/i);
  await page.getByRole("button", { name: "1M", exact: true }).click();
  await expect(page.getByRole("button", { name: "1M", exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.getByRole("button", { name: "3M", exact: true }).click();
  await expect(page.getByRole("button", { name: "3M", exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  await page.getByRole("link", { name: "Start demo debate", exact: true }).click();
  await expect(page).toHaveURL(/\/debates\/demo-aapl/);
  const savedResponse = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/history" && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Start replay", exact: true }).click();
  await expect(page.getByText("Saved to your history", { exact: true })).toBeVisible();
  const response = await savedResponse;
  expect(response.fromServiceWorker()).toBe(true);
  const saved = (await response.json()) as { id: string };
  await expect(
    page.getByRole("region", { name: "Debate replay" }).getByRole("article"),
  ).toHaveCount(5);

  await page.getByRole("link", { name: "View saved sessions" }).click();
  await expect(page).toHaveURL(/\/history$/);
  const savedLink = page.locator(`main a[href="/debates/${encodeURIComponent(saved.id)}"]`);
  await expect(savedLink).toBeVisible();
  await savedLink.click();
  await expect(page).toHaveURL(new RegExp(`/debates/${saved.id}$`));
  await expect(page.getByRole("button", { name: "Start replay", exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("button", { name: "Start replay", exact: true })).toBeVisible();
  expect(pageErrors).toEqual([]);
});
