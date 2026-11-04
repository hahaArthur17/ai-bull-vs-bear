import { delay, http, HttpResponse } from "msw";
import { feedbackSchema } from "@/features/feedback/model/feedback.schema";
import { acceptAttachments } from "@/features/feedback/model/attachment-policy";
import type { FeedbackReceipt } from "@/features/feedback/api/feedback.contract";

const receipts = new Map<string, { fingerprint: string; receipt: FeedbackReceipt }>();

async function fingerprintOf(value: unknown) {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(JSON.stringify(value)),
  );
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function receiveFeedback(request: Request) {
  const scenario = request.headers.get("X-Demo-Scenario");
  await delay(scenario === "slow" ? 3500 : 450);
  if (scenario === "error") return HttpResponse.json({ code: "demo_failure" }, { status: 500 });
  if (scenario === "field-error")
    return HttpResponse.json(
      { fieldErrors: { title: "Please make the title a little more specific." } },
      { status: 422 },
    );
  const body = await request.formData();
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(String(body.get("feedback")));
  } catch {
    return HttpResponse.json({ code: "invalid_payload" }, { status: 422 });
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload))
    return HttpResponse.json({ code: "invalid_payload" }, { status: 422 });
  const parsed = feedbackSchema.safeParse({
    ...payload,
    fullName: payload.fullName ?? "",
    email: payload.email ?? "",
    gender: payload.gender ?? "",
    relatedPage: payload.relatedPage ?? "",
    reproductionSteps: payload.reproductionSteps ?? "",
    expectedResult: payload.expectedResult ?? "",
    actualResult: payload.actualResult ?? "",
  });
  if (!parsed.success)
    return HttpResponse.json(
      {
        code: "invalid_fields",
        fieldErrors: Object.fromEntries(
          parsed.error.issues.map((issue) => [issue.path[0], issue.message]),
        ),
      },
      { status: 422 },
    );
  const files = body.getAll("attachments").filter((file): file is File => typeof file !== "string");
  const validation = acceptAttachments([], files);
  if (validation.issues.length)
    return HttpResponse.json(
      { code: "invalid_attachments" },
      { status: validation.issues.some((issue) => issue.code === "type") ? 415 : 413 },
    );
  const key = request.headers.get("Idempotency-Key");
  if (!key) return HttpResponse.json({ code: "missing_idempotency_key" }, { status: 422 });
  const fingerprint = await fingerprintOf([
    payload,
    files.map((file) => [file.name, file.size, file.type]),
  ]);
  const previous = receipts.get(key);
  if (previous && previous.fingerprint !== fingerprint)
    return HttpResponse.json({ code: "idempotency_conflict" }, { status: 409 });
  if (previous) return HttpResponse.json(previous.receipt, { status: 201 });
  const receipt: FeedbackReceipt = {
    id: `demo_feedback_${crypto.randomUUID().slice(0, 8)}`,
    mode: "demo",
    status: "simulated",
    submittedAt: new Date().toISOString(),
    attachmentCount: files.length,
  };
  if (receipts.size >= 100) receipts.delete(receipts.keys().next().value!);
  receipts.set(key, { fingerprint, receipt });
  return HttpResponse.json(receipt, { status: 201 });
}

export const feedbackHandlers = [
  http.post("/api/feedback", ({ request }) => receiveFeedback(request)),
];
