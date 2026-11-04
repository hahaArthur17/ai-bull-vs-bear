import { Search, SlidersHorizontal } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function UniverseHeading({
  count,
  onlySaved,
  onViewChange,
}: {
  count?: number;
  onlySaved: boolean;
  onViewChange: (value: string) => void;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 className="section-title">
          Your research universe
          <span className="ml-3 rounded-full bg-secondary px-2 py-0.5 align-middle text-[10px] font-medium text-muted-foreground">
            {count ?? "—"}
          </span>
        </h2>
        <p className="mt-1.5 text-xs text-muted-foreground">
          Pick a company. Find a different perspective.
        </p>
      </div>
      <div className="flex gap-1 rounded-lg border p-1">
        <Button
          size="sm"
          variant={onlySaved ? "ghost" : "secondary"}
          className="h-7 text-[10px]"
          onClick={() => onViewChange("")}
        >
          All companies
        </Button>
        <Button
          size="sm"
          variant={onlySaved ? "secondary" : "ghost"}
          className="h-7 text-[10px]"
          onClick={() => onViewChange("watchlist")}
        >
          My watchlist
        </Button>
      </div>
    </div>
  );
}

export function UniverseFilters({
  query,
  sector,
  sectors,
  onQueryChange,
  onSectorChange,
}: {
  query: string;
  sector: string;
  sectors: string[];
  onQueryChange: (value: string) => void;
  onSectorChange: (value: string) => void;
}) {
  return (
    <div className="mb-4 flex flex-wrap gap-3">
      <div className="relative min-w-44 flex-1">
        <Search className="absolute left-3 top-3 size-4 text-muted-foreground" aria-hidden="true" />
        <Input
          className="h-10 bg-card pl-9 text-xs"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          aria-label="Search stocks"
          placeholder="Search companies or tickers…"
        />
      </div>
      <Select value={sector} onValueChange={onSectorChange}>
        <SelectTrigger className="h-10 w-44 bg-card text-xs" aria-label="Filter by sector">
          <SlidersHorizontal className="size-3" />
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All sectors</SelectItem>
          {sectors.map((item) => (
            <SelectItem key={item} value={item}>
              {item}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
