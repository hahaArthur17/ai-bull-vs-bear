import { ArrowUpRight, FileText } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { Evidence } from "@/lib/contracts/research";
import { sourceUrl } from "../model/role-presentation";

export function DebateEvidenceDialog({
  evidence,
  open,
  onOpenChange,
  loading,
  error,
  onRetry,
}: {
  evidence?: Evidence;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  loading: boolean;
  error: boolean;
  onRetry: () => void;
}) {
  const url = sourceUrl(evidence?.url);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <div className="mb-3 flex size-10 items-center justify-center rounded-xl bg-secondary text-primary">
            <FileText size={18} />
          </div>
          <DialogTitle className="font-serif text-2xl leading-tight">
            {evidence?.title ?? "Supporting evidence"}
          </DialogTitle>
          <DialogDescription>
            {loading
              ? "Loading supporting evidence…"
              : evidence
                ? `${evidence.type} · ${evidence.date} · demonstration excerpt`
                : "This evidence is unavailable in the current replay."}
          </DialogDescription>
        </DialogHeader>
        {evidence && (
          <blockquote className="border-l-2 border-primary/30 pl-4 text-sm leading-7 text-muted-foreground">
            {evidence.excerpt}
          </blockquote>
        )}
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-sm font-medium text-primary underline-offset-4 hover:underline"
          >
            Visit source <ArrowUpRight size={15} />
          </a>
        )}
        {error && (
          <Button variant="outline" onClick={onRetry}>
            Try loading evidence again
          </Button>
        )}
        <p className="text-xs leading-5 text-muted-foreground">
          This excerpt is part of a prepared research example. It is not live market evidence.
        </p>
      </DialogContent>
    </Dialog>
  );
}
