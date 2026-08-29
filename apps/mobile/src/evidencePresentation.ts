import { formatMarketDate } from "./dateFormat.ts";
import type { EvidenceItem } from "./types";

export type EvidencePresentation = {
  date: string;
  freshness: string;
  source: string;
  tone: "current" | "stale" | "unknown";
};

export function presentEvidence(item: EvidenceItem): EvidencePresentation {
  const source = typeof item.metadata.source === "string" && item.metadata.source.trim()
    ? item.metadata.source
    : `${item.source_type} source`;
  const date = item.published_at ? formatMarketDate(item.published_at) : "Date unavailable";
  const age = item.freshness.age_days;
  const evaluatedAt = item.freshness.evaluated_at
    ? ` · assessed ${formatMarketDate(item.freshness.evaluated_at)}`
    : "";

  if (item.freshness.status === "current") {
    return { source, date, tone: "current", freshness: `Current${age === null || age === undefined ? "" : ` · ${age}d old`}${evaluatedAt}` };
  }
  if (item.freshness.status === "stale") {
    return { source, date, tone: "stale", freshness: `Stale${age === null || age === undefined ? "" : ` · ${age}d old`}${evaluatedAt}` };
  }
  return { source, date, tone: "unknown", freshness: `Freshness unavailable${evaluatedAt}` };
}
