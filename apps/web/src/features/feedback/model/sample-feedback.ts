import { defaultFeedback } from "./feedback.schema";
import type { FeedbackValues } from "./feedback.schema";

export const sampleFeedback: FeedbackValues = {
  ...defaultFeedback,
  category: "suggestion",
  title: "A side-by-side view for saved research",
  description:
    "I’d love to compare the Bull and Bear summaries for two stocks side by side. It would make it easier to spot how their main risks differ without switching between pages.",
  relatedPage: "research",
  experienceRating: 4,
};
