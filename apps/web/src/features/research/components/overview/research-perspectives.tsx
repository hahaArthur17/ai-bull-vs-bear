import { ArrowDownRight, ArrowUpRight, Scale } from "lucide-react";
import { Link } from "react-router-dom";
import type { StockResearch } from "@/lib/contracts/research";

export function ResearchPerspectives({ research }: { research: StockResearch }) {
  return (
    <section className="surface flex h-full flex-col p-6">
      <div className="mb-6 flex items-center gap-2">
        <Scale className="size-4 text-primary" />
        <h2 className="text-sm font-medium">Consider both sides</h2>
      </div>
      <div>
        <p className="mb-3 inline-flex items-center gap-2 rounded-full bg-bull/10 px-2.5 py-1 text-[10px] font-medium text-bull">
          <ArrowUpRight className="size-3" />
          The bull perspective
        </p>
        <p className="text-xs leading-[1.8] text-muted-foreground">{research.bullCase}</p>
      </div>
      <div className="my-6 border-t" />
      <div>
        <p className="mb-3 inline-flex items-center gap-2 rounded-full bg-bear/10 px-2.5 py-1 text-[10px] font-medium text-bear">
          <ArrowDownRight className="size-3" />
          The bear perspective
        </p>
        <p className="text-xs leading-[1.8] text-muted-foreground">{research.bearCase}</p>
      </div>
      <div className="mt-auto pt-6">
        <p className="text-[9px] leading-relaxed text-muted-foreground">
          Illustrative arguments, not live analysis or a recommendation.
        </p>
        {research.stock.coverage === "ready" && (
          <Link
            to={`/debates/demo-${research.stock.ticker.toLowerCase()}?ticker=${research.stock.ticker}`}
            className="mt-4 inline-flex items-center gap-2 text-xs font-medium text-primary"
          >
            See the conversation unfold
            <ArrowUpRight className="size-3" />
          </Link>
        )}
      </div>
    </section>
  );
}
