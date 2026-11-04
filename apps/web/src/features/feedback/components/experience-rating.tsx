import { Controller, useFormContext } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import type { FeedbackValues } from "../model/feedback.schema";

const ratings = ["Very difficult", "Difficult", "Neutral", "Easy", "Very easy"];

export function ExperienceRating() {
  const { control } = useFormContext<FeedbackValues>();
  return (
    <Controller
      name="experienceRating"
      control={control}
      render={({ field }) => (
        <fieldset className="space-y-3">
          <legend className="text-sm font-medium">
            How has your experience been?{" "}
            <span className="font-normal text-muted-foreground">(optional)</span>
          </legend>
          <RadioGroup
            value={field.value?.toString() ?? ""}
            onValueChange={(value) => field.onChange(Number(value))}
            className="grid grid-cols-2 gap-2 sm:grid-cols-5"
          >
            {ratings.map((label, index) => (
              <Label
                key={label}
                htmlFor={`rating-${index + 1}`}
                className="flex cursor-pointer flex-col items-start gap-2 rounded-lg border p-3 text-xs has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-primary/5"
              >
                <RadioGroupItem id={`rating-${index + 1}`} value={String(index + 1)} />
                {label}
              </Label>
            ))}
          </RadioGroup>
          {field.value !== null && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-auto px-0 text-xs"
              onClick={() => field.onChange(null)}
            >
              Clear rating
            </Button>
          )}
        </fieldset>
      )}
    />
  );
}
