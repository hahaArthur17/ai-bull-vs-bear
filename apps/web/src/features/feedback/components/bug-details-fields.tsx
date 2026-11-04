import { FormTextField } from "./form-text-field";

export function BugDetailsFields() {
  return (
    <div className="space-y-5 rounded-xl border border-dashed bg-muted/35 p-5">
      <p className="text-sm font-medium">Help us reproduce the issue</p>
      <FormTextField
        name="reproductionSteps"
        label="Steps to reproduce *"
        placeholder="1. Open the research page…"
        multiline
        maxLength={2000}
        description="At least 10 characters. Include what you clicked before the issue."
      />
      <div className="grid gap-5 sm:grid-cols-2">
        <FormTextField
          name="expectedResult"
          label="Expected result (optional)"
          multiline
          maxLength={1000}
        />
        <FormTextField
          name="actualResult"
          label="Actual result (optional)"
          multiline
          maxLength={1000}
        />
      </div>
    </div>
  );
}
