import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export function FeedbackSection({
  number,
  title,
  description,
  children,
}: {
  number: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <Card className="gap-0 overflow-hidden border-border/80 shadow-none">
      <CardHeader className="border-b bg-muted/15 px-5 py-5 sm:px-7">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/8 text-xs font-semibold text-primary">
            {number}
          </span>
          <div>
            <CardTitle className="text-base font-semibold">{title}</CardTitle>
            <CardDescription className="mt-1.5 text-xs leading-relaxed">
              {description}
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="px-5 py-6 sm:px-7">{children}</CardContent>
    </Card>
  );
}
