import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import type { Stock } from "@/lib/contracts/research";
import { money, percent } from "@/lib/format/market";
import { WatchlistButton } from "@/features/watchlist/components/watchlist-button";

export function StockTable({ stocks }: { stocks: Stock[] }) {
  return (
    <div className="surface overflow-hidden">
      <div
        className="relative overflow-x-auto"
        role="region"
        aria-label="Research companies"
        tabIndex={0}
      >
        <table className="stock-table">
          <caption className="sr-only">
            Research stocks with synthetic prices, changes and coverage
          </caption>
          <thead>
            <tr>
              <th>Company</th>
              <th>Price</th>
              <th>Change</th>
              <th className="hidden lg:table-cell">Sector</th>
              <th className="hidden sm:table-cell">Coverage</th>
              <th>
                <span className="sr-only">Save</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {stocks.map((stock) => (
              <tr key={stock.ticker}>
                <td className="company-cell">
                  <Link
                    to={`/stocks/${stock.ticker}`}
                    className="group flex min-w-28 items-center gap-2 sm:min-w-40 sm:gap-3"
                  >
                    <span className="stock-symbol !size-8 shrink-0 sm:!size-10">
                      {stock.ticker.slice(0, 2)}
                    </span>
                    <span className="min-w-0">
                      <span className="flex items-center gap-2 text-xs font-semibold">
                        {stock.ticker}
                        <ArrowUpRight className="size-3 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                      </span>
                      <span className="mt-1 block text-[11px] text-muted-foreground">
                        {stock.name}
                      </span>
                    </span>
                  </Link>
                </td>
                <td className="numeric whitespace-nowrap text-xs font-medium">
                  {money(stock.price)}
                </td>
                <td
                  className={`numeric whitespace-nowrap text-xs ${stock.changePercent >= 0 ? "positive" : "negative"}`}
                >
                  {percent(stock.changePercent)}
                </td>
                <td className="hidden text-[11px] text-muted-foreground lg:table-cell">
                  {stock.sector}
                </td>
                <td className="hidden sm:table-cell">
                  <Badge
                    variant="secondary"
                    className={`border-0 text-[9px] font-medium ${stock.coverage === "ready" ? "bg-accent text-primary" : "bg-muted text-muted-foreground"}`}
                  >
                    {stock.coverage === "ready" ? "Research ready" : "Limited data"}
                  </Badge>
                </td>
                <td>
                  <WatchlistButton ticker={stock.ticker} compact />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
