import { Link, useParams } from "react-router-dom";
import { useResearch } from "@/features/research/hooks";
import { StockHeader } from "@/features/research/components/overview/stock-header";
import { ResearchMetrics } from "@/features/research/components/overview/research-metrics";
import { ResearchPerspectives } from "@/features/research/components/overview/research-perspectives";
import { PriceChartPanel } from "@/features/research/components/charts/price-chart-panel";
import { EvidenceBoard } from "@/features/evidence/components/evidence-board";
import { PageLoading } from "@/components/shared/status/page-loading";
import { ErrorState } from "@/components/shared/status/error-state";

export function ResearchPage() {
  const { ticker = "AAPL" } = useParams();
  const query = useResearch(ticker.toUpperCase());
  if (query.isPending) return <PageLoading />;
  if (query.isError)
    return (
      <div className="page-content">
        <Link to="/" className="quiet-link mb-6 inline-block">
          ← Back to workspace
        </Link>
        <ErrorState message={query.error.message} retry={() => void query.refetch()} />
      </div>
    );
  const research = query.data;
  return (
    <div className="page-content">
      <StockHeader stock={research.stock} />
      <ResearchMetrics research={research} />
      <div className="grid items-stretch gap-5 xl:grid-cols-[1.65fr_1fr]">
        <PriceChartPanel prices={research.prices} />
        <ResearchPerspectives research={research} />
      </div>
      <EvidenceBoard evidence={research.evidence} />
    </div>
  );
}
