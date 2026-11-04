import { useFormContext, useWatch } from "react-hook-form";
import { categoryOptions, pageOptions } from "../model/feedback.schema";
import type { FeedbackValues } from "../model/feedback.schema";
import { FormTextField } from "./form-text-field";
import { FormSelectField } from "./form-select-field";
import { ExperienceRating } from "./experience-rating";
import { BugDetailsFields } from "./bug-details-fields";

export function FeedbackDetailsFields() {
  const { control } = useFormContext<FeedbackValues>();
  const category = useWatch({ control, name: "category" });
  return (
    <div className="space-y-6">
      <div className="grid gap-5 sm:grid-cols-2">
        <FormSelectField
          name="category"
          label="Feedback type *"
          placeholder="What would you like to share?"
          options={categoryOptions}
        />
        <FormSelectField
          name="relatedPage"
          label="Related page (optional)"
          placeholder="Choose a page"
          options={pageOptions}
          optional
        />
      </div>
      <FormTextField
        name="title"
        label="Give it a short title *"
        placeholder="e.g. Compare two research summaries"
        maxLength={100}
      />
      <FormTextField
        name="description"
        label="Tell us more *"
        placeholder="What could work better? A little context goes a long way."
        description="At least 20 characters. Please leave out sensitive information."
        multiline
        maxLength={3000}
      />
      {category === "bug" && <BugDetailsFields />}
      <ExperienceRating />
    </div>
  );
}
