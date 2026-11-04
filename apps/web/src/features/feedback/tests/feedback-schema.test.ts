import { describe, expect, it } from "vitest";
import { defaultFeedback, feedbackSchema } from "../model/feedback.schema";
import { sampleFeedback } from "../model/sample-feedback";
import { toFeedbackPayload } from "../api/feedback.mapper";

describe("feedback validation", () => {
  it("requires useful feedback but allows anonymous contact details", () => {
    expect(feedbackSchema.safeParse(defaultFeedback).success).toBe(false);
    expect(feedbackSchema.safeParse(sampleFeedback).success).toBe(true);
    expect(toFeedbackPayload(sampleFeedback)).toMatchObject({
      fullName: null,
      email: null,
      gender: null,
    });
  });

  it("requires a valid email only when a reply is requested", () => {
    expect(feedbackSchema.safeParse({ ...sampleFeedback, wantsReply: true }).success).toBe(false);
    expect(
      feedbackSchema.safeParse({ ...sampleFeedback, wantsReply: true, email: "avery@example.com" })
        .success,
    ).toBe(true);
    expect(feedbackSchema.safeParse({ ...sampleFeedback, email: "not-an-email" }).success).toBe(
      false,
    );
  });

  it("requires reproduction steps for bugs and omits hidden bug fields otherwise", () => {
    expect(feedbackSchema.safeParse({ ...sampleFeedback, category: "bug" }).success).toBe(false);
    expect(
      feedbackSchema.safeParse({
        ...sampleFeedback,
        category: "bug",
        reproductionSteps: "Open the research page and change the date range.",
      }).success,
    ).toBe(true);
    expect(
      toFeedbackPayload({ ...sampleFeedback, reproductionSteps: "A previous bug draft" })
        .reproductionSteps,
    ).toBeNull();
  });

  it("accepts international names and trims submitted fields", () => {
    const result = feedbackSchema.parse({
      ...sampleFeedback,
      fullName: "  李 明  ",
      title: "  A useful improvement  ",
    });
    expect(result.fullName).toBe("李 明");
    expect(result.title).toBe("A useful improvement");
  });

  it("checks content lengths and optional rating boundaries", () => {
    expect(feedbackSchema.safeParse({ ...sampleFeedback, title: "x".repeat(101) }).success).toBe(
      false,
    );
    expect(
      feedbackSchema.safeParse({ ...sampleFeedback, description: "x".repeat(19) }).success,
    ).toBe(false);
    expect(feedbackSchema.safeParse({ ...sampleFeedback, experienceRating: 0 }).success).toBe(
      false,
    );
    expect(
      feedbackSchema.safeParse({
        ...sampleFeedback,
        experienceRating: null,
        gender: "prefer_not_to_say",
      }).success,
    ).toBe(true);
  });
});
