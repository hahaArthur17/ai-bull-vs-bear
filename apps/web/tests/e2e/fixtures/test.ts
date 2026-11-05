import { test as base, expect } from "@playwright/test";

export const test = base.extend<{ pageErrors: string[] }>({
  pageErrors: async ({ page }, provide) => {
    const errors: string[] = [];
    const collect = (error: Error) => errors.push(error.message);
    page.on("pageerror", collect);
    await provide(errors);
    page.off("pageerror", collect);
  },
});

export { expect };
