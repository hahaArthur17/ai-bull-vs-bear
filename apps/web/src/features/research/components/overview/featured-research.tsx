import { lazy, Suspense } from "react";
import { ArrowRight, ArrowUpRight, CircleDot } from "lucide-react";
import { Link } from "react-router-dom";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useResearch } from "../../hooks";
import { money, percent } from "@/lib/format/market";

const PriceChart = lazy(() => import("../charts/price-chart"));

export function FeaturedResearch() {
  const { data, isError } = useResearch("AAPL");
  return (
    <div className="mb-10 grid gap-5 xl:grid-cols-[1.65fr_1fr]">
      <section className="surface overflow-hidden">
        <div className="flex items-center justify-between border-b px-6 py-4">
          <p className="eyebrow">In focus</p>
          <Link
            to="/stocks/AAPL"
            className="quiet-link inline-flex items-center gap-1 !text-[11px]"
          >
            Open research
            <ArrowUpRight className="size-3" />
          </Link>
        </div>
        <div className="px-6 pt-5">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="stock-symbol !size-11 !rounded-full">A</span>
              <div>
                <h2 className="text-sm font-semibold">Apple Inc.</h2>
                <p className="mt-1 text-[10px] text-muted-foreground">AAPL · Technology</p>
              </div>
            </div>
            {data && (
              <div className="text-right numeric">
                <p className="text-xl font-semibold tracking-tight">{money(data.stock.price)}</p>
                <p className="mt-1 text-[10px] positive">
                  {percent(data.stock.changePercent)} · Demo session
                </p>
              </div>
            )}
          </div>
          {data ? (
            <div className="mt-5">
              <Suspense fallback={<Skeleton className="h-36" />}>
                <PriceChart points={data.prices.slice(-65)} compact />
              </Suspense>
              <p className="pb-4 text-[9px] text-muted-foreground">
                3-month synthetic history · not live market data
              </p>
            </div>
          ) : (
            <div className="py-8 text-xs text-muted-foreground">
              {isError ? (
                "A new perspective is a click away. Open a company to begin."
              ) : (
                <Skeleton className="h-28" />
              )}
            </div>
          )}
        </div>
      </section>
      <PerspectiveCard />
    </div>
  );
}

function PerspectiveCard() {
  return (
    <section className="relative flex flex-col justify-between overflow-hidden rounded-xl bg-[#194f43] p-7 text-[#f1f6e8]">
      <div>
        <p className="flex items-center gap-2 text-[9px] font-medium uppercase tracking-[0.18em] text-[#bdd4be]">
          <CircleDot className="size-3" />
          The power of a counterpoint
        </p>
        <h2 className="font-editorial mt-5 text-[29px] leading-[1.17] tracking-tight">
          One company.
          <br />
          Two perspectives.
          <br />
          <span className="text-[#c9dfa1]">A better question.</span>
        </h2>
        <p className="mt-4 max-w-64 text-[11px] leading-relaxed text-[#d1dfd3]">
          Follow the bull case. Challenge it with the bear case. Explore the evidence in between.
        </p>
      </div>
      <Button
        asChild
        variant="secondary"
        size="sm"
        className="mt-6 w-fit border-0 bg-[#d6e8b8] text-[11px] text-[#1b4130] hover:bg-[#e3efcf]"
      >
        <Link to="/debates/demo-aapl?ticker=AAPL">
          Explore a demo debate <ArrowRight className="size-3" />
        </Link>
      </Button>
    </section>
  );
}
