import { Skeleton } from "@/components/ui/skeleton";

export function PageLoading() {
  return (
    <div className="page-content space-y-6" role="status" aria-label="Loading page">
      <Skeleton className="h-12 w-64" />
      <Skeleton className="h-5 w-80 max-w-full" />
      <Skeleton className="h-80 w-full rounded-xl" />
      <span className="sr-only">Loading research workspace…</span>
    </div>
  );
}
