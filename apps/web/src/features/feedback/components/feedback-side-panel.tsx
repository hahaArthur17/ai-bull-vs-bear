import { Check, LockKeyhole, MessageSquareText } from "lucide-react";
import { config } from "@/app/config/env";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { DemoScenario } from "../api/feedback.contract";

type Props = {
  scenario: DemoScenario;
  onScenarioChange: (scenario: DemoScenario) => void;
  disabled: boolean;
};
const scenarios: { value: DemoScenario; label: string }[] = [
  { value: "normal", label: "Successful submission" },
  { value: "error", label: "Service error" },
  { value: "slow", label: "Slow response" },
  { value: "field-error", label: "Field validation error" },
];

export function FeedbackSidePanel({ scenario, onScenarioChange, disabled }: Props) {
  const isDemo = config.feedbackMode === "demo";
  return (
    <aside className="space-y-6 lg:sticky lg:top-8 lg:self-start">
      <div className="rounded-2xl bg-primary p-6 text-primary-foreground">
        <MessageSquareText className="mb-5 size-6 opacity-80" aria-hidden="true" />
        <h2 className="font-serif text-2xl leading-tight">
          A better workspace
          <br />
          starts with your ideas.
        </h2>
        <p className="mt-3 text-sm leading-relaxed opacity-80">
          Tell us what felt useful, what got in the way, or what you wish existed.
        </p>
        <ul className="mt-6 space-y-3 text-xs">
          {["Suggestions, big or small", "Screenshots that add context", "No account needed"].map(
            (text) => (
              <li key={text} className="flex items-center gap-2">
                <Check className="size-3.5 opacity-70" />
                {text}
              </li>
            ),
          )}
        </ul>
      </div>
      <div className="rounded-xl border p-5">
        <div className="flex items-center gap-2 text-sm font-medium">
          <LockKeyhole className="size-4 text-primary" />
          Your details are optional
        </div>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          Only add an email if you’d like a reply. Please avoid including passwords, financial
          account details or private documents.
        </p>
      </div>
      {isDemo && (
        <div className="space-y-3 rounded-xl border border-dashed p-5">
          <Badge variant="secondary">Interactive demo</Badge>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Try an error or a slow response to explore how the form recovers. Nothing is sent to the
            developer.
          </p>
          <Label htmlFor="feedback-scenario" className="text-xs">
            Submission scenario
          </Label>
          <Select
            value={scenario}
            onValueChange={(value) => onScenarioChange(value as DemoScenario)}
            disabled={disabled}
          >
            <SelectTrigger id="feedback-scenario" className="w-full bg-background">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {scenarios.map((option) => (
                <SelectItem value={option.value} key={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
    </aside>
  );
}
