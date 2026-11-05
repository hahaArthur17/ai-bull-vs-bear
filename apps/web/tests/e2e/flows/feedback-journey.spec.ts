import { test, expect } from "../fixtures/test";
import { demoAttachments } from "../fixtures/attachments";
import { captureQaScreenshot } from "../fixtures/screenshots";

test("the user-page entry leads to a validated feedback demo with attachments", async ({
  page,
  pageErrors,
}) => {
  await page.goto("/user");
  const entry = page.getByRole("link", { name: "Send feedback", exact: true });
  await entry.scrollIntoViewIfNeeded();
  await entry.click();
  await expect(page).toHaveURL(/\/feedback$/);
  await captureQaScreenshot(page, "feedback-form");

  await page.getByRole("button", { name: "Try demo submission", exact: true }).click();
  await expect(page.getByText("A few details need your attention", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Fill sample feedback", exact: true }).click();
  await page
    .getByLabel("Choose feedback attachments", { exact: true })
    .setInputFiles(demoAttachments());
  const attachments = page.getByRole("list", { name: "Selected attachments" });
  await expect(attachments.getByText("demo-chart.png", { exact: true })).toBeVisible();
  await expect(attachments.getByText("demo-feedback.pdf", { exact: true })).toBeVisible();

  const receiptResponse = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/feedback" &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Try demo submission", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "You’ve completed the feedback demo." }),
  ).toBeVisible();
  const receipt = await receiptResponse;
  expect(receipt.fromServiceWorker()).toBe(true);
  expect(await receipt.json()).toMatchObject({
    mode: "demo",
    status: "simulated",
    attachmentCount: 2,
  });
  await expect(
    page.getByText("Nothing was sent to the developer or stored on a server.", { exact: false }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Send another feedback", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "Give it a short title *", exact: true }),
  ).toHaveValue("");
  await expect(page.getByRole("list", { name: "Selected attachments" })).toHaveCount(0);
  await page.getByRole("link", { name: "Back to user page", exact: true }).click();
  await expect(page).toHaveURL(/\/user#feedback$/);
  await expect(page.getByRole("link", { name: "Send feedback", exact: true })).toBeInViewport();
  expect(pageErrors).toEqual([]);
});

test("reply details, conditional bug fields and reset preserve deliberate choices", async ({
  page,
  pageErrors,
}) => {
  await page.goto("/feedback");
  await page.getByRole("button", { name: "Fill sample feedback", exact: true }).click();
  await page.getByRole("checkbox", { name: "I’d like a reply", exact: true }).check();
  await page.getByRole("button", { name: "Try demo submission", exact: true }).click();
  const email = page.getByRole("textbox", { name: "Email address *", exact: true });
  await expect(email).toHaveAttribute("aria-invalid", "true");
  await expect(email).toBeFocused();
  await email.fill("avery.chen@example.com");

  await page.getByRole("combobox", { name: "Feedback type *", exact: true }).click();
  await page.getByRole("option", { name: "Something isn’t working", exact: true }).click();
  const steps = page.getByRole("textbox", { name: "Steps to reproduce *", exact: true });
  await expect(steps).toBeVisible();
  await steps.fill("Open research, switch range, and inspect the chart.");
  await page.getByRole("combobox", { name: "Feedback type *", exact: true }).click();
  await page.getByRole("option", { name: "An idea or suggestion", exact: true }).click();
  await expect(steps).toHaveCount(0);

  await page.getByRole("button", { name: "Reset form", exact: true }).click();
  const confirmation = page.getByRole("alertdialog", { name: "Clear this feedback?" });
  await confirmation.getByRole("button", { name: "Keep editing", exact: true }).click();
  await expect(email).toHaveValue("avery.chen@example.com");
  await page.getByRole("button", { name: "Reset form", exact: true }).click();
  await confirmation.getByRole("button", { name: "Reset form", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "Email address (optional)", exact: true }),
  ).toHaveValue("");
  await expect(
    page.getByRole("checkbox", { name: "I’d like a reply", exact: true }),
  ).not.toBeChecked();
  await expect(
    page.getByRole("textbox", { name: "Give it a short title *", exact: true }),
  ).toHaveValue("");
  expect(pageErrors).toEqual([]);
});

test("a failed feedback submission retains the draft and can be retried", async ({
  page,
  pageErrors,
}) => {
  await page.goto("/feedback");
  await page.getByRole("button", { name: "Fill sample feedback", exact: true }).click();
  await page.getByRole("combobox", { name: "Submission scenario", exact: true }).click();
  await page.getByRole("option", { name: "Service error", exact: true }).click();
  await page.getByRole("button", { name: "Try demo submission", exact: true }).click();
  await expect(page.getByText("We couldn’t finish this submission", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "Give it a short title *", exact: true }),
  ).toHaveValue("A side-by-side view for saved research");
  await page.getByRole("combobox", { name: "Submission scenario", exact: true }).click();
  await page.getByRole("option", { name: "Successful submission", exact: true }).click();
  await page.getByRole("button", { name: "Retry submission", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "You’ve completed the feedback demo." }),
  ).toBeVisible();
  expect(pageErrors).toEqual([]);
});
