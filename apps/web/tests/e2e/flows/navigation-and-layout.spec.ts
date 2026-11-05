import { test, expect } from "../fixtures/test";
import { captureQaScreenshot } from "../fixtures/screenshots";

test("deep links remain usable after a full refresh", async ({ page, pageErrors }) => {
  for (const path of ["/stocks/AAPL", "/user", "/feedback", "/history"]) {
    await page.goto(path);
    const heading = page.getByRole("main").getByRole("heading", { level: 1 });
    await expect(heading).toBeVisible();
    const title = await heading.innerText();
    await page.reload();
    await expect(heading).toHaveText(title);
    await expect(page).toHaveURL(new RegExp(`${path}$`));
  }
  expect(pageErrors).toEqual([]);
});

test("theme changes persist through refresh", async ({ page, pageErrors }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Switch to dark theme", exact: true }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.getByRole("button", { name: "Switch to light theme", exact: true }).click();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  expect(pageErrors).toEqual([]);
});

test("mobile navigation works and primary pages stay within a 390px viewport", async ({
  page,
  pageErrors,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Open navigation", exact: true }).click();
  const navigation = page.getByRole("dialog", { name: "Navigation", exact: true });
  await navigation.getByRole("link", { name: "Your space", exact: true }).click();
  await expect(page).toHaveURL(/\/user$/);
  await expect(navigation).not.toBeVisible();
  for (const path of [
    "/",
    "/stocks/AAPL",
    "/debates/demo-aapl",
    "/history",
    "/user",
    "/feedback",
  ]) {
    await page.goto(path);
    await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toBeVisible();
    if (path === "/")
      await expect(
        page.getByRole("main").getByText("Apple Inc.", { exact: true }).first(),
      ).toBeVisible();
    if (path.startsWith("/stocks/"))
      await expect(page.getByRole("region", { name: "Price history", exact: true })).toBeVisible();
    if (path.startsWith("/debates/"))
      await expect(page.getByRole("button", { name: "Start replay", exact: true })).toBeVisible();
    if (path === "/history")
      await expect(page.getByRole("link", { name: /^Reopen / }).first()).toBeVisible();
    await page.evaluate(() => document.fonts.ready.then(() => undefined));
    if (path === "/") await captureQaScreenshot(page, "mobile-home");
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), {
        message: `${path} should not overflow horizontally`,
      })
      .toBe(true);
  }
  expect(pageErrors).toEqual([]);
});
