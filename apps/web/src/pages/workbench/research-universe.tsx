import { useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useStocks } from "@/features/research/hooks";
import { useWatchlist } from "@/features/watchlist/hooks";
import { StockTable } from "@/features/research/components/overview/stock-table";
import { EmptyState } from "@/components/shared/status/empty-state";
import { ErrorState } from "@/components/shared/status/error-state";
import { UniverseHeading, UniverseFilters } from "./universe-controls";

export function ResearchUniverse() {
  const [params, setParams] = useSearchParams();
  const sector = params.get("sector") ?? "all";
  const query = params.get("q") ?? "";
  const onlySaved = params.get("view") === "watchlist";
  const result = useStocks(query);
  const catalog = useStocks("");
  const sectors = [...new Set(catalog.data?.map((stock) => stock.sector) ?? [])];
  const watchlist = useWatchlist();
  const visible = result.data?.filter(
    (stock) =>
      (!onlySaved || watchlist.data?.includes(stock.ticker)) &&
      (sector === "all" || stock.sector === sector),
  );
  function updateParam(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true, preventScrollReset: true });
  }
  return (
    <section id="research-universe">
      <UniverseHeading
        count={result.data?.length}
        onlySaved={onlySaved}
        onViewChange={(value) => updateParam("view", value)}
      />
      <UniverseFilters
        query={query}
        sector={sector}
        sectors={sectors}
        onQueryChange={(value) => updateParam("q", value)}
        onSectorChange={(value) => updateParam("sector", value)}
      />
      {result.isPending ? (
        <Skeleton className="h-80 w-full" />
      ) : result.isError ? (
        <ErrorState message={result.error.message} retry={() => void result.refetch()} />
      ) : visible?.length ? (
        <StockTable stocks={visible} />
      ) : (
        <EmptyState
          title={onlySaved ? "Make a little room for curiosity." : "No companies found."}
          description={
            onlySaved
              ? "Save a company using its bookmark button, then find it here."
              : "Try another company name or clear the filters."
          }
          action={
            <Button
              variant="outline"
              onClick={() => {
                const next = new URLSearchParams(params);
                next.delete("sector");
                next.delete("q");
                setParams(next, { replace: true, preventScrollReset: true });
              }}
            >
              Clear filters
            </Button>
          }
        />
      )}
      <p className="mt-4 text-[10px] text-muted-foreground">
        Prices and research are synthetic examples. Coverage labels describe available demo
        features.
      </p>
    </section>
  );
}
