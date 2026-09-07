import { formatMarketDate } from "./dateFormat.ts";
import type { DebateEvidencePresentation, EvidenceItem } from "./types";

export type EvidencePresentation = {
  date: string;
  freshness: string;
  source: string;
  tone: "current" | "stale" | "unknown";
};

export type DebateEvidenceView = EvidencePresentation & {
  evidenceId: string;
  evidenceType: DebateEvidencePresentation["evidence_type"];
  title: string | null;
  fact: string | null;
  supportSpan: string | null;
  sourceDestination: string | null;
  missingMetadata: DebateEvidencePresentation["missing_metadata"];
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

export function presentDebateEvidence(
  item: DebateEvidencePresentation,
): DebateEvidenceView {
  const age = item.freshness.age_days;
  const evaluatedAt = item.freshness.evaluated_at
    ? ` · assessed ${formatMarketDate(item.freshness.evaluated_at)}`
    : "";
  let freshness = `Freshness unavailable${evaluatedAt}`;
  if (item.freshness.status === "current") {
    freshness = `Current${age === null || age === undefined ? "" : ` · ${age}d old`}${evaluatedAt}`;
  } else if (item.freshness.status === "stale") {
    freshness = `Stale${age === null || age === undefined ? "" : ` · ${age}d old`}${evaluatedAt}`;
  }
  return {
    evidenceId: item.evidence_id,
    evidenceType: item.evidence_type,
    title: item.title,
    fact: item.fact,
    source: item.source ?? "Source unavailable",
    date: item.date ? formatMarketDate(item.date) : "Date unavailable",
    freshness,
    tone: item.freshness.status,
    supportSpan: item.support_span,
    sourceDestination: item.source_destination,
    missingMetadata: item.missing_metadata,
  };
}
