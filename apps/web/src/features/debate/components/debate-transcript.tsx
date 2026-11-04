import { ArrowDown, MessagesSquare, Scale } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { DebateMessage as Message } from "@/lib/contracts/research";
import { useTranscriptFollow } from "../hooks/use-transcript-follow";
import { DebateMessage } from "./debate-message";

export function DebateTranscript({
  messages,
  onEvidence,
}: {
  messages: Message[];
  onEvidence: (id: string) => void;
}) {
  const { viewportRef, following, onScroll, jumpToLatest } = useTranscriptFollow(messages.length);
  return (
    <div className="relative">
      <div
        ref={viewportRef}
        onScroll={onScroll}
        tabIndex={0}
        aria-label="Debate transcript"
        className="max-h-[620px] min-h-[400px] overflow-y-auto px-5 py-7 focus-visible:outline-2 focus-visible:outline-primary sm:min-h-[460px] sm:px-7"
      >
        {messages.length ? (
          <div className="space-y-7">
            {messages.map((message, index) => (
              <DebateMessage
                key={message.id}
                message={message}
                index={index}
                onEvidence={onEvidence}
              />
            ))}
          </div>
        ) : (
          <TranscriptWelcome />
        )}
      </div>
      {!following && messages.length > 0 && (
        <div className="pointer-events-none absolute inset-x-0 bottom-4 flex justify-center">
          <Button
            size="sm"
            variant="secondary"
            className="pointer-events-auto rounded-full border shadow-sm"
            onClick={jumpToLatest}
          >
            <ArrowDown size={14} /> Jump to latest
          </Button>
        </div>
      )}
    </div>
  );
}

function TranscriptWelcome() {
  return (
    <div className="mx-auto flex min-h-[340px] max-w-sm flex-col items-center justify-center text-center">
      <div className="mb-6 flex size-16 items-center justify-center rounded-full border bg-secondary/60 text-primary">
        <Scale size={27} strokeWidth={1.5} />
      </div>
      <h2 className="font-serif text-3xl leading-tight">
        A good thesis deserves
        <br />a counterargument.
      </h2>
      <p className="mt-4 text-sm leading-6 text-muted-foreground">
        Follow two perspectives, inspect their evidence, and make room for a more balanced view.
      </p>
      <span className="mt-6 inline-flex items-center gap-2 text-xs text-muted-foreground">
        <MessagesSquare size={14} /> Press Start replay to enter the discussion
      </span>
    </div>
  );
}
