import { Link, useRouteError } from "react-router-dom";
import { Button } from "@/components/ui/button";

export function RouteError() {
  const error = useRouteError();
  return (
    <div className="page-content flex min-h-[70vh] flex-col justify-center">
      <p className="eyebrow mb-3">A moment to regroup</p>
      <h1 className="page-title">Something needs another look.</h1>
      <p role="alert" className="mb-7 mt-4 max-w-lg text-sm leading-relaxed text-muted-foreground">
        {error instanceof Error
          ? error.message
          : "The page could not be opened. Please return to the workspace and try again."}
      </p>
      <Button asChild className="w-fit">
        <Link to="/">Return to workspace</Link>
      </Button>
    </div>
  );
}
