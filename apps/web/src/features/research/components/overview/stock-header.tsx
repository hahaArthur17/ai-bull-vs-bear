import { ArrowLeft, ArrowUpRight, MessagesSquare } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { WatchlistButton } from "@/features/watchlist/components/watchlist-button";
import { money, percent } from "@/lib/format/market";
import type { Stock } from "@/lib/contracts/research";

export function StockHeader({ stock }: { stock: Stock }) {
  return (
    <header className="mb-8">
      <Link to="/" className="quiet-link mb-7 inline-flex items-center gap-2 !text-xs">
        <ArrowLeft className="size-3" />
        Back to workspace
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-6">
        <div>
          <div className="mb-4 flex items-center gap-3">
            <span className="stock-symbol !size-12 !rounded-full !text-lg">{stock.ticker[0]}</span>
            <div>
              <p className="eyebrow">
                {stock.ticker} · {stock.sector}
              </p>
              <Badge variant="secondary" className="mt-2 border-0 text-[9px] font-normal">
                {stock.coverage === "ready" ? "Research ready" : "Limited demo coverage"}
              </Badge>
            </div>
          </div>
          <h1 className="page-title">{stock.name}</h1>
          <div className="mt-4 flex flex-wrap items-baseline gap-3 numeric">
            <span className="text-3xl font-medium tracking-tight">{money(stock.price)}</span>
            <span
              className={`inline-flex items-center gap-1 text-xs ${stock.changePercent >= 0 ? "positive" : "negative"}`}
            >
              <ArrowUpRight className={`size-3 ${stock.changePercent < 0 ? "rotate-90" : ""}`} />
              {stock.change >= 0 ? "+" : ""}
              {stock.change.toFixed(2)} ({percent(stock.changePercent)})
            </span>
            <span className="text-[10px] text-muted-foreground">USD · Demo close</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 pt-1">
          <WatchlistButton ticker={stock.ticker} />
          {stock.coverage === "ready" ? (
            <Button asChild size="sm">
              <Link to={`/debates/demo-${stock.ticker.toLowerCase()}?ticker=${stock.ticker}`}>
                <MessagesSquare className="size-4" />
                Start demo debate
              </Link>
            </Button>
          ) : (
            <Button size="sm" disabled>
              Debate unavailable
            </Button>
          )}
        </div>
      </div>
      <p className="mt-5 max-w-2xl text-xs leading-relaxed text-muted-foreground">
        {stock.description}
      </p>
    </header>
  );
}
