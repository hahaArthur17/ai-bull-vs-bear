import { lazy, Suspense, useState } from "react";
import { ChartNoAxesCombined } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { PricePoint } from "@/lib/contracts/research";
import { marketDate, money } from "@/lib/format/market";

const PriceChart = lazy(() => import("./price-chart"));
const ranges = { "1M": 22, "3M": 65, "6M": 130, "1Y": 262 } as const;

export function PriceChartPanel({ prices }: { prices: PricePoint[] }) {
  const [range, setRange] = useState<keyof typeof ranges>("3M");
  const points = prices.slice(-ranges[range]);
  if (points.length < 2)
    return (
      <p className="p-6 text-sm text-muted-foreground">
        Not enough labelled price history is available.
      </p>
    );
  return (
    <section className="surface p-5 sm:p-6" aria-label="Price history">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <h2 className="flex items-center gap-2 text-sm font-medium">
          <ChartNoAxesCombined className="size-4 text-primary" />
          Price history
        </h2>
        <div className="flex gap-1 rounded-lg bg-muted p-1" aria-label="Chart time range">
          {Object.keys(ranges).map((item) => (
            <Button
              key={item}
              variant={item === range ? "outline" : "ghost"}
              size="sm"
              aria-pressed={item === range}
              className="h-7 min-w-10 border-transparent px-3 text-[11px] shadow-none"
              onClick={() => setRange(item as keyof typeof ranges)}
            >
              {item}
            </Button>
          ))}
        </div>
      </div>
      <Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <PriceChart points={points} />
      </Suspense>
      <div className="mt-4 flex flex-wrap justify-between gap-2 text-[10px] text-muted-foreground">
        <span>USD · Synthetic closing prices</span>
        <span>
          {marketDate(points[0].date)} — {marketDate(points.at(-1)!.date)}
        </span>
      </div>
      <details className="mt-5 border-t pt-4 text-xs">
        <summary className="cursor-pointer text-muted-foreground">
          View chart data · latest 10 points
        </summary>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left numeric">
            <caption className="sr-only">Last ten selected closing prices in US dollars</caption>
            <thead>
              <tr className="text-muted-foreground">
                <th className="py-2 font-medium">Date</th>
                <th className="text-right font-medium">Close (USD)</th>
              </tr>
            </thead>
            <tbody>
              {points.slice(-10).map((point) => (
                <tr key={point.date} className="border-t">
                  <td className="py-2">{marketDate(point.date)}</td>
                  <td className="text-right">{money(point.close)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
