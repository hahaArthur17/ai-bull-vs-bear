import type { FeedbackValues } from "../model/feedback.schema";

export function toFeedbackPayload(values: FeedbackValues) {
  const isBug = values.category === "bug";
  return {
    ...values,
    fullName: values.fullName.trim() || null,
    email: values.email.trim() || null,
    gender: values.gender || null,
    relatedPage: values.relatedPage || null,
    reproductionSteps: isBug ? values.reproductionSteps : null,
    expectedResult: isBug ? values.expectedResult || null : null,
    actualResult: isBug ? values.actualResult || null : null,
  };
}

export function toFeedbackFormData(values: FeedbackValues, files: File[]) {
  const body = new FormData();
  body.set("feedback", JSON.stringify(toFeedbackPayload(values)));
  files.forEach((file) => body.append("attachments", file));
  return body;
}
