import { Quote } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { DebateMessage as Message } from "@/lib/contracts/research";
import { rolePresentation, roundLabel } from "../model/role-presentation";

export function DebateMessage({
  message,
  index,
  onEvidence,
}: {
  message: Message;
  index: number;
  onEvidence: (id: string) => void;
}) {
  const role = rolePresentation[message.role];
  return (
    <article
      className="flex gap-3 sm:gap-4"
      aria-label={`${role.label}, ${roundLabel(message.role, index)}`}
    >
      <div
        className={`flex size-10 shrink-0 items-center justify-center rounded-full border text-xs font-bold ${role.className}`}
        aria-hidden="true"
      >
        {role.initials}
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-sm font-semibold">{role.label}</h3>
          <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
            {roundLabel(message.role, index)}
          </span>
        </div>
        <div className="rounded-2xl rounded-tl-sm border bg-card p-4 sm:p-5">
          <p className="whitespace-pre-line text-sm leading-7 text-foreground/85">
            {message.content}
          </p>
          {message.evidenceId && (
            <Button
              variant="ghost"
              size="sm"
              className="mt-3 -ml-2 h-8 text-xs text-primary"
              onClick={() => onEvidence(message.evidenceId!)}
            >
              <Quote size={13} /> Read supporting evidence
            </Button>
          )}
        </div>
      </div>
    </article>
  );
}
