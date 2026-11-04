import { ArrowUpRight, BookOpen, SearchX } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export function HistoryEmpty({ filtered, onReset }: { filtered: boolean; onReset: () => void }) {
  return (
    <div className="rounded-2xl border border-dashed bg-card px-6 py-16 text-center">
      <div className="mx-auto mb-5 flex size-14 items-center justify-center rounded-full bg-secondary text-primary">
        {filtered ? (
          <SearchX size={23} strokeWidth={1.5} />
        ) : (
          <BookOpen size={23} strokeWidth={1.5} />
        )}
      </div>
      <h2 className="font-serif text-3xl">
        {filtered ? "A fresh search might help." : "Your thinking, collected."}
      </h2>
      <p className="mx-auto mt-3 max-w-sm text-sm leading-6 text-muted-foreground">
        {filtered
          ? "No saved sessions match these filters. Try another stock or a different search."
          : "Finish a debate replay to keep its perspectives and summary here for another look."}
      </p>
      {filtered ? (
        <Button variant="outline" className="mt-6" onClick={onReset}>
          Clear filters
        </Button>
      ) : (
        <Button asChild className="mt-6">
          <Link to="/">
            Explore stocks <ArrowUpRight size={15} />
          </Link>
        </Button>
      )}
    </div>
  );
}
