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

function isPublicIpv4Address(hostname: string): boolean {
  const octets = hostname.split(".").map(Number);
  if (octets.length !== 4 || !octets.every((octet) => Number.isInteger(octet) && octet >= 0 && octet <= 255)) return true;

  const [first, second, third] = octets;
  return !(
    first === 0
    || first === 10
    || first === 127
    || (first === 100 && second >= 64 && second <= 127)
    || (first === 169 && second === 254)
    || (first === 172 && second >= 16 && second <= 31)
    || (first === 192 && second === 0 && third === 0)
    || (first === 192 && second === 0 && third === 2)
    || (first === 192 && second === 168)
    || (first === 198 && (second === 18 || second === 19))
    || (first === 198 && second === 51 && third === 100)
    || (first === 203 && second === 0 && third === 113)
    || first >= 224
  );
}

function isPublicIpv6Address(hostname: string): boolean {
  if (!hostname.includes(":")) return true;
  const normalized = hostname.replace(/^\[|\]$/g, "").toLowerCase();
  const [first = "", second = ""] = normalized.split(":");
  const firstValue = Number.parseInt(first, 16);
  const secondValue = Number.parseInt(second || "0", 16);

  if (!Number.isFinite(firstValue) || firstValue < 0x2000 || firstValue > 0x3fff) return false;
  if (firstValue === 0x2001 && (secondValue <= 0x01ff || secondValue === 0x0db8)) return false;
  return firstValue !== 0x3ffe;
}

export function isSafeEvidenceDestination(value: string | null | undefined): value is string {
  if (!value || value !== value.trim() || /\s/.test(value)) return false;
  try {
    const destination = new URL(value);
    if (destination.protocol !== "https:" || destination.username || destination.password) return false;

    const hostname = destination.hostname.toLowerCase().replace(/^\[|\]$/g, "");
    if (!hostname || hostname === "localhost" || hostname.endsWith(".localhost") || hostname.endsWith(".local") || hostname.endsWith(".internal")) return false;
    return isPublicIpv4Address(hostname) && isPublicIpv6Address(hostname);
  } catch {
    return false;
  }
}

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
