import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function HistoryFilters({
  query,
  ticker,
  tickers,
  onQuery,
  onTicker,
}: {
  query: string;
  ticker: string;
  tickers: string[];
  onQuery: (value: string) => void;
  onTicker: (value: string) => void;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row">
      <div className="relative flex-1">
        <Search
          size={16}
          className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          aria-label="Search saved sessions"
          value={query}
          onChange={(event) => onQuery(event.target.value)}
          placeholder="Search your research…"
          className="h-11 bg-card pl-10"
        />
      </div>
      <Select value={ticker} onValueChange={onTicker}>
        <SelectTrigger aria-label="Filter history by stock" className="h-11 w-full bg-card sm:w-44">
          <SelectValue placeholder="All stocks" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All stocks</SelectItem>
          {tickers.map((item) => (
            <SelectItem key={item} value={item}>
              {item}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
