import type { ReactNode } from "react";
import { SearchX } from "lucide-react";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex min-h-56 flex-col items-center justify-center rounded-xl border border-dashed px-6 py-12 text-center">
      <SearchX className="mb-4 size-7 text-muted-foreground" aria-hidden="true" />
      <h2 className="font-medium">{title}</h2>
      <p className="mb-5 mt-2 max-w-sm text-sm text-muted-foreground">{description}</p>
      {action}
    </div>
  );
}
