import { useFormContext, useWatch } from "react-hook-form";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { FeedbackValues } from "../model/feedback.schema";

type TextName =
  | "title"
  | "description"
  | "reproductionSteps"
  | "expectedResult"
  | "actualResult"
  | "fullName"
  | "email";
type Props = {
  name: TextName;
  label: string;
  description?: string;
  placeholder?: string;
  multiline?: boolean;
  maxLength?: number;
  type?: "text" | "email";
  autoComplete?: string;
};

export function FormTextField({ name, label, description, multiline, ...props }: Props) {
  const {
    register,
    formState: { errors },
    control,
  } = useFormContext<FeedbackValues>();
  const value = useWatch({ control, name });
  const error = errors[name];
  const id = `feedback-${name}`;
  const inputProps = {
    ...register(name),
    ...props,
    id,
    "aria-invalid": Boolean(error),
    "aria-describedby": `${id}-description${error ? ` ${id}-error` : ""}`,
  };
  return (
    <Field data-invalid={Boolean(error)} className="gap-2">
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      {multiline ? (
        <Textarea {...inputProps} className="min-h-28 resize-y bg-background" />
      ) : (
        <Input {...inputProps} className="h-11 bg-background" />
      )}
      <div
        id={`${id}-description`}
        className="flex justify-between gap-3 text-xs text-muted-foreground"
      >
        <FieldDescription className="text-xs">{description}</FieldDescription>
        {multiline && props.maxLength && (
          <span className="shrink-0 tabular-nums">
            {value.length}/{props.maxLength}
          </span>
        )}
      </div>
      {error && <FieldError id={`${id}-error`}>{error.message}</FieldError>}
    </Field>
  );
}
