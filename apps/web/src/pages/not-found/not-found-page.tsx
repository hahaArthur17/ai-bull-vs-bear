import { ArrowLeft, Compass } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <div className="page-content flex min-h-[65vh] flex-col items-center justify-center text-center">
      <Compass className="mb-6 size-10 text-primary" />
      <p className="eyebrow mb-3">A small detour</p>
      <h1 className="page-title">Let’s find your perspective.</h1>
      <p className="mb-7 mt-4 max-w-sm text-sm leading-relaxed text-muted-foreground">
        This page isn’t in the workspace. There’s still plenty to explore.
      </p>
      <Button asChild>
        <Link to="/">
          <ArrowLeft className="size-4" />
          Back to workspace
        </Link>
      </Button>
    </div>
  );
}
