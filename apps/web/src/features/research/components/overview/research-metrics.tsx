import type { StockResearch } from "@/lib/contracts/research";

export function ResearchMetrics({ research }: { research: StockResearch }) {
  const fallback = [
    { label: "Market cap", value: research.stock.marketCap, detail: "Synthetic market snapshot" },
    { label: "P/E ratio", value: research.stock.pe, detail: "Illustrative valuation" },
  ];
  const items = research.metrics.length ? research.metrics : fallback;
  return (
    <section className="mb-7 grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="Key indicators">
      {items.slice(0, 4).map((item) => (
        <div key={item.label} className="surface p-4 sm:p-5">
          <p className="eyebrow !text-[9px] !tracking-[0.1em]">{item.label}</p>
          <p className="numeric my-3 text-xl font-medium tracking-tight">{item.value}</p>
          <p className="text-[10px] leading-relaxed text-muted-foreground">{item.detail}</p>
        </div>
      ))}
    </section>
  );
}
