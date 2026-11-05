import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { expect, type Page } from "@playwright/test";

export async function captureQaScreenshot(page: Page, name: string) {
  const directory = process.env.QA_SCREENSHOT_DIR;
  if (!directory) return;
  await expect(page.locator('[data-slot="skeleton"]')).toHaveCount(0);
  if (name.endsWith("home")) {
    await expect(page.getByRole("img", { name: /^Synthetic closing prices/ })).toBeVisible();
    await expect(page.locator(".recharts-area-curve")).toHaveCount(1);
  }
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
  await mkdir(directory, { recursive: true });
  await page.screenshot({ path: join(directory, `${name}.png`), fullPage: true });
}
