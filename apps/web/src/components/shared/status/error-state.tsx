import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div role="alert" className="rounded-xl border border-destructive/25 bg-destructive/5 p-6">
      <AlertCircle className="mb-3 size-5 text-destructive" aria-hidden="true" />
      <h2 className="font-medium">We couldn’t load this just yet.</h2>
      <p className="mb-4 mt-2 text-sm text-muted-foreground">{message}</p>
      {retry && (
        <Button variant="outline" size="sm" onClick={retry}>
          Try again
        </Button>
      )}
    </div>
  );
}
