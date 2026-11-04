import { ArrowUpRight, Bookmark, MessageSquareText, Telescope } from "lucide-react";
import { Link } from "react-router-dom";
import { useWatchlist } from "@/features/watchlist/hooks";
import { useHistory } from "@/features/history/hooks";
import { useStocks } from "@/features/research/hooks";
import { FeaturedResearch } from "@/features/research/components/overview/featured-research";
import { ResearchUniverse } from "./research-universe";

export function WorkbenchPage() {
  return (
    <div className="page-content">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="eyebrow mb-3">Your research workspace</p>
          <h1 className="page-title">
            Your research,
            <br className="sm:hidden" /> with a{" "}
            <em className="font-normal text-primary">counterpoint.</em>
          </h1>
          <p className="mt-3 text-xs text-muted-foreground">
            A thoughtful space to explore companies, challenge ideas, and see both sides.
          </p>
        </div>
        <Link to="/user" className="quiet-link inline-flex items-center gap-1 !text-xs">
          Make yourself at home <ArrowUpRight className="size-3" />
        </Link>
      </header>
      <WorkspaceStats />
      <FeaturedResearch />
      <ResearchUniverse />
    </div>
  );
}

function WorkspaceStats() {
  const watchlist = useWatchlist();
  const history = useHistory();
  const stocks = useStocks("");
  const items = [
    { label: "In your watchlist", value: watchlist.data?.length, icon: Bookmark },
    {
      label: "Ready to explore",
      value: stocks.data?.filter((stock) => stock.coverage === "ready").length,
      icon: Telescope,
    },
    { label: "Saved conversations", value: history.data?.length, icon: MessageSquareText },
  ];
  return (
    <div className="mb-8 flex flex-wrap gap-y-4 border-y py-5">
      {items.map((item) => (
        <div key={item.label} className="hero-stat flex items-center gap-3">
          <item.icon className="hidden size-4 text-muted-foreground sm:block" />
          <div>
            <p className="eyebrow !text-[8px] !tracking-[0.12em]">{item.label}</p>
            <p className="numeric mt-1 text-lg font-medium tracking-tight">
              {item.value === undefined ? "—" : String(item.value).padStart(2, "0")}
            </p>
          </div>
        </div>
      ))}
      <div className="ml-auto hidden items-center text-right text-[10px] leading-relaxed text-muted-foreground xl:flex">
        A sample market, a real experience.
        <br />
        Demo dataset · 30 Oct 2026
      </div>
    </div>
  );
}
