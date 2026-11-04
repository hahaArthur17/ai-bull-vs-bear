import { useEffect, useState } from "react";
import { Search, ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useStocks } from "@/features/research/hooks";

export function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const result = useStocks(query);
  useEffect(() => {
    const handle = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      }
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, []);
  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        className="gap-3 text-muted-foreground"
        onClick={() => setOpen(true)}
        aria-label="Search stocks"
      >
        <Search className="size-4" />
        <span className="hidden lg:inline">Search anything</span>
        <kbd className="hidden rounded border px-1.5 py-0.5 text-[10px] md:block">⌘ K</kbd>
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Find your next perspective</DialogTitle>
          </DialogHeader>
          <Input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search a company or ticker…"
            aria-label="Search company or ticker"
          />
          <div className="max-h-80 overflow-y-auto">
            {result.isError ? (
              <p role="alert" className="p-4 text-sm">
                Search is unavailable. Try again shortly.
              </p>
            ) : result.data?.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">No companies found.</p>
            ) : (
              result.data?.map((stock) => (
                <Link
                  key={stock.ticker}
                  to={`/stocks/${stock.ticker}`}
                  onClick={() => setOpen(false)}
                  className="flex items-center gap-3 rounded-lg p-3 hover:bg-accent"
                >
                  <span className="stock-symbol">{stock.ticker.slice(0, 2)}</span>
                  <span className="flex-1 text-sm">
                    <strong className="block">{stock.ticker}</strong>
                    <span className="text-muted-foreground">{stock.name}</span>
                  </span>
                  <ArrowUpRight className="size-4" />
                </Link>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
