import { z } from "zod";
import type { FeedbackValues } from "../model/feedback.schema";

export const feedbackReceiptSchema = z.object({
  id: z.string().min(1),
  mode: z.enum(["demo", "api"]),
  status: z.enum(["simulated", "received"]),
  submittedAt: z.iso.datetime(),
  attachmentCount: z.number().int().min(0).max(3),
});

export type FeedbackReceipt = z.infer<typeof feedbackReceiptSchema>;
export type DemoScenario = "normal" | "error" | "slow" | "field-error";
export type FeedbackFieldErrors = Partial<Record<keyof FeedbackValues, string>>;

export class FeedbackRequestError extends Error {
  constructor(
    message: string,
    public fieldErrors: FeedbackFieldErrors = {},
  ) {
    super(message);
    this.name = "FeedbackRequestError";
  }
}
