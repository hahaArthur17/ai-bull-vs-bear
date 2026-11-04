import { Controller, useFormContext, useWatch } from "react-hook-form";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { genderOptions } from "../model/feedback.schema";
import type { FeedbackValues } from "../model/feedback.schema";
import { FormTextField } from "./form-text-field";
import { FormSelectField } from "./form-select-field";

export function OptionalContactFields() {
  const { control } = useFormContext<FeedbackValues>();
  const wantsReply = useWatch({ control, name: "wantsReply" });
  return (
    <div className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        <FormTextField
          name="fullName"
          label="Your name (optional)"
          placeholder="How should we address you?"
          maxLength={80}
          autoComplete="name"
        />
        <FormSelectField
          name="gender"
          label="Gender (optional)"
          placeholder="Prefer to leave it blank"
          options={genderOptions}
          optional
          description="This never affects how feedback is prioritised."
        />
      </div>
      <Controller
        name="wantsReply"
        control={control}
        render={({ field }) => (
          <div className="flex items-start gap-3 rounded-lg bg-muted/50 p-4">
            <Checkbox
              id="feedback-wants-reply"
              checked={field.value}
              onCheckedChange={(value) => field.onChange(value === true)}
              ref={field.ref}
              onBlur={field.onBlur}
              className="mt-0.5"
            />
            <div className="space-y-1">
              <Label htmlFor="feedback-wants-reply">I’d like a reply</Label>
              <p className="text-xs leading-relaxed text-muted-foreground">
                Add your email below. This won’t subscribe you to anything.
              </p>
            </div>
          </div>
        )}
      />
      <FormTextField
        name="email"
        label={`Email address ${wantsReply ? "*" : "(optional)"}`}
        type="email"
        autoComplete="email"
        placeholder="you@example.com"
        description={
          wantsReply
            ? "Required so we can reply. Demo mode never sends email."
            : "You can leave this blank if you don’t need a reply."
        }
      />
    </div>
  );
}
