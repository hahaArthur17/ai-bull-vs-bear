import { Controller, useFormContext } from "react-hook-form";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { FeedbackValues } from "../model/feedback.schema";

type Props = {
  name: "category" | "relatedPage" | "gender";
  label: string;
  placeholder: string;
  options: readonly { value: string; label: string }[];
  description?: string;
  optional?: boolean;
};

export function FormSelectField({
  name,
  label,
  placeholder,
  options,
  description,
  optional,
}: Props) {
  const { control } = useFormContext<FeedbackValues>();
  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <Field data-invalid={fieldState.invalid} className="gap-2">
          <FieldLabel htmlFor={`feedback-${name}`}>{label}</FieldLabel>
          <Select
            value={field.value ?? ""}
            onValueChange={(value) => field.onChange(value === "not-selected" ? "" : value)}
          >
            <SelectTrigger
              id={`feedback-${name}`}
              ref={field.ref}
              onBlur={field.onBlur}
              className="h-11 w-full bg-background"
              aria-invalid={fieldState.invalid}
              aria-describedby={`feedback-${name}-description${fieldState.error ? ` feedback-${name}-error` : ""}`}
            >
              <SelectValue placeholder={placeholder} />
            </SelectTrigger>
            <SelectContent>
              {optional && <SelectItem value="not-selected">Not specified</SelectItem>}
              {options.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FieldDescription id={`feedback-${name}-description`} className="text-xs">
            {description}
          </FieldDescription>
          {fieldState.error && (
            <FieldError id={`feedback-${name}-error`}>{fieldState.error.message}</FieldError>
          )}
        </Field>
      )}
    />
  );
}
