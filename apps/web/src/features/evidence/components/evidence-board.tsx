import { useState } from "react";
import { ArrowUpRight, FileText, Newspaper, ChartNoAxesCombined, LibraryBig } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Evidence } from "@/lib/contracts/research";
import { marketDate } from "@/lib/format/market";

const icons = { filing: FileText, news: Newspaper, technical: ChartNoAxesCombined };

export function EvidenceBoard({ evidence }: { evidence: Evidence[] }) {
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState<Evidence | null>(null);
  const visible = evidence.filter((item) => filter === "all" || item.type === filter);
  return (
    <section className="mt-9" aria-label="Evidence board">
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <h2 className="section-title flex items-center gap-2">
            <LibraryBig className="size-4 text-primary" />
            Behind the perspectives
          </h2>
          <p className="mt-2 text-xs text-muted-foreground">
            Examine the examples behind each argument.
          </p>
        </div>
        <Select value={filter} onValueChange={setFilter}>
          <SelectTrigger aria-label="Filter evidence" className="w-36 bg-card text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All evidence</SelectItem>
            <SelectItem value="filing">Filings</SelectItem>
            <SelectItem value="news">News</SelectItem>
            <SelectItem value="technical">Technical</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {visible.map((item) => (
          <EvidenceTile key={item.id} item={item} onOpen={() => setSelected(item)} />
        ))}
      </div>
      {visible.length === 0 && (
        <p className="surface p-6 text-sm text-muted-foreground">
          No sample evidence in this category.
        </p>
      )}
      <Sheet
        open={!!selected}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
          <SheetHeader className="p-6 pb-2">
            <Badge variant="secondary" className="mb-4 w-fit text-[10px]">
              Synthetic evidence · {selected?.type}
            </Badge>
            <SheetTitle className="font-editorial text-2xl leading-tight">
              {selected?.title}
            </SheetTitle>
            <SheetDescription>
              {selected ? marketDate(selected.date) : ""} · Illustrative research note
            </SheetDescription>
          </SheetHeader>
          <div className="px-6 py-4">
            <p className="whitespace-pre-wrap text-sm leading-7 text-muted-foreground">
              {selected?.excerpt}
            </p>
            <div className="mt-8 rounded-lg bg-muted p-4 text-xs leading-relaxed text-muted-foreground">
              This note is part of the synthetic demonstration dataset. It is not a verified
              quotation from a live source.
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </section>
  );
}

function EvidenceTile({ item, onOpen }: { item: Evidence; onOpen: () => void }) {
  const Icon = icons[item.type];
  return (
    <button
      type="button"
      onClick={onOpen}
      className="surface group flex flex-col p-5 text-left transition-colors hover:border-primary/40"
    >
      <span className="mb-4 flex w-full items-center justify-between">
        <Icon className="size-5 text-primary" />
        <ArrowUpRight className="size-3 text-muted-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
      </span>
      <span className="eyebrow mb-2 !text-[8px]">{item.type}</span>
      <span className="text-sm font-medium leading-relaxed">{item.title}</span>
      <span className="mt-3 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
        {item.excerpt}
      </span>
      <span className="mt-auto pt-5 text-[9px] text-muted-foreground">
        {marketDate(item.date)} · Demo source
      </span>
    </button>
  );
}
