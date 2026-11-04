import { z } from "zod";

export const categoryOptions = [
  { value: "suggestion", label: "An idea or suggestion" },
  { value: "bug", label: "Something isn’t working" },
  { value: "usability", label: "My experience using the app" },
  { value: "other", label: "Something else" },
] as const;

export const pageOptions = [
  { value: "workspace", label: "Research workspace" },
  { value: "research", label: "Stock research" },
  { value: "debate", label: "Bull vs Bear debate" },
  { value: "history", label: "Research history" },
  { value: "user", label: "User page" },
  { value: "other", label: "Another page" },
] as const;

export const genderOptions = [
  { value: "woman", label: "Woman" },
  { value: "man", label: "Man" },
  { value: "non_binary", label: "Non-binary" },
  { value: "prefer_not_to_say", label: "Prefer not to say" },
] as const;

export const feedbackSchema = z
  .object({
    category: z.enum(["", "suggestion", "bug", "usability", "other"]),
    title: z.string().trim().min(5, "Add a title of at least 5 characters.").max(100),
    description: z
      .string()
      .trim()
      .min(20, "Tell us a little more: at least 20 characters.")
      .max(3000),
    relatedPage: z.enum(["", "workspace", "research", "debate", "history", "user", "other"]),
    experienceRating: z.number().int().min(1).max(5).nullable(),
    reproductionSteps: z.string().trim().max(2000),
    expectedResult: z.string().trim().max(1000),
    actualResult: z.string().trim().max(1000),
    fullName: z.string().trim().max(80, "Use 80 characters or fewer."),
    email: z
      .string()
      .trim()
      .max(254)
      .refine(
        (value) => !value || z.email().safeParse(value).success,
        "Enter a valid email address.",
      ),
    gender: z.enum(["", "woman", "man", "non_binary", "prefer_not_to_say"]),
    wantsReply: z.boolean(),
  })
  .superRefine((values, ctx) => {
    if (!values.category)
      ctx.addIssue({ code: "custom", path: ["category"], message: "Choose a feedback type." });
    if (values.category === "bug" && values.reproductionSteps.length < 10) {
      ctx.addIssue({
        code: "custom",
        path: ["reproductionSteps"],
        message: "Add at least 10 characters describing the steps.",
      });
    }
    if (values.wantsReply && !values.email) {
      ctx.addIssue({
        code: "custom",
        path: ["email"],
        message: "Add an email address so we can reply.",
      });
    }
  });

export type FeedbackValues = z.infer<typeof feedbackSchema>;

export const defaultFeedback: FeedbackValues = {
  category: "",
  title: "",
  description: "",
  relatedPage: "",
  experienceRating: null,
  reproductionSteps: "",
  expectedResult: "",
  actualResult: "",
  fullName: "",
  email: "",
  gender: "",
  wantsReply: false,
};
