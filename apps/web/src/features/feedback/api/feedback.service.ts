import { config } from "@/app/config/env";
import { feedbackReceiptSchema, FeedbackRequestError } from "./feedback.contract";
import type { DemoScenario, FeedbackFieldErrors } from "./feedback.contract";
import { toFeedbackFormData } from "./feedback.mapper";
import { defaultFeedback } from "../model/feedback.schema";
import type { FeedbackValues } from "../model/feedback.schema";

async function readRequestError(response: Response) {
  const payload = (await response.json().catch(() => null)) as {
    fieldErrors?: Record<string, unknown>;
  } | null;
  const fields: FeedbackFieldErrors = {};
  for (const [key, value] of Object.entries(payload?.fieldErrors ?? {})) {
    if (Object.hasOwn(defaultFeedback, key) && typeof value === "string")
      fields[key as keyof FeedbackValues] = value;
  }
  const message =
    response.status === 429
      ? "Too many attempts. Please try again shortly."
      : response.status === 422
        ? "Check the highlighted fields and try again."
        : response.status === 413
          ? "Your attachments exceed the upload limits."
          : "Your feedback could not be submitted. Your draft is still here.";
  return new FeedbackRequestError(message, fields);
}

export async function submitFeedback(
  values: FeedbackValues,
  files: File[],
  options: {
    signal: AbortSignal;
    idempotencyKey: string;
    scenario: DemoScenario;
  },
) {
  if (config.feedbackMode === "disabled")
    throw new FeedbackRequestError("Feedback submission is not connected yet.");
  const base =
    config.feedbackMode === "demo" ? "/api" : config.feedbackApiBaseUrl.replace(/\/$/, "");
  if (!base) throw new FeedbackRequestError("The feedback service is not configured.");
  const headers: Record<string, string> = { "Idempotency-Key": options.idempotencyKey };
  if (config.feedbackMode === "demo") headers["X-Demo-Scenario"] = options.scenario;
  let response: Response;
  try {
    response = await fetch(`${base}/feedback`, {
      method: "POST",
      body: toFeedbackFormData(values, files),
      headers,
      signal: AbortSignal.any([options.signal, AbortSignal.timeout(15000)]),
    });
  } catch (error) {
    if (options.signal.aborted) throw error;
    throw new FeedbackRequestError(
      error instanceof DOMException && error.name === "TimeoutError"
        ? "The request timed out. Retry safely with the same submission."
        : "We couldn’t connect. Your feedback and files are still here to retry.",
    );
  }
  if (!response.ok) throw await readRequestError(response);
  const parsed = feedbackReceiptSchema.safeParse(await response.json().catch(() => null));
  const expectedStatus = config.feedbackMode === "demo" ? "simulated" : "received";
  if (
    !parsed.success ||
    parsed.data.mode !== config.feedbackMode ||
    parsed.data.status !== expectedStatus
  ) {
    throw new FeedbackRequestError(
      "The service returned an unexpected receipt. Please retry safely.",
    );
  }
  return parsed.data;
}
