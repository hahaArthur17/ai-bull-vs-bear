import assert from "node:assert/strict";
import test from "node:test";

import { presentDebateEvidence, presentEvidence } from "./evidencePresentation.ts";
import type { DebateEvidencePresentation, EvidenceItem } from "./types.ts";

function evidence(overrides: Partial<EvidenceItem> = {}): EvidenceItem {
  return {
    id: "E1",
    ticker: "MSFT",
    source_type: "news",
    title: "Evidence title",
    excerpt: "Evidence excerpt",
    metadata: { source: "Reuters" },
    published_at: "2026-08-29T00:00:00Z",
    freshness: { status: "current", age_days: 1, evaluated_at: "2026-08-30T00:00:00Z" },
    ...overrides,
  };
}

test("evidence presentation preserves source, dated provenance, and freshness", () => {
  const result = presentEvidence(evidence());

  assert.equal(result.source, "Reuters");
  assert.equal(result.date, "Aug 29, 2026");
  assert.equal(result.tone, "current");
  assert.match(result.freshness, /1d old/);
  assert.match(result.freshness, /assessed Aug 30, 2026/);
});

test("evidence presentation makes missing dates and stale data explicit", () => {
  const result = presentEvidence(evidence({
    source_type: "filing",
    metadata: {},
    published_at: null,
    freshness: { status: "stale", age_days: 90 },
  }));

  assert.equal(result.source, "filing source");
  assert.equal(result.date, "Date unavailable");
  assert.equal(result.tone, "stale");
  assert.match(result.freshness, /Stale · 90d old/);
});

test("Debate evidence presentation preserves server-declared missing metadata without inference", () => {
  const item: DebateEvidencePresentation = {
    evidence_id: "retained-old-citation",
    evidence_type: null,
    title: null,
    fact: null,
    source: null,
    date: null,
    freshness: { status: "unknown" },
    support_span: null,
    source_destination: null,
    missing_metadata: [
      "evidence_type",
      "title",
      "fact",
      "source",
      "date",
      "support_span",
      "source_destination",
    ],
  };

  const result = presentDebateEvidence(item);

  assert.equal(result.source, "Source unavailable");
  assert.equal(result.fact, null);
  assert.equal(result.date, "Date unavailable");
  assert.equal(result.freshness, "Freshness unavailable");
  assert.equal(result.supportSpan, null);
  assert.deepEqual(result.missingMetadata, item.missing_metadata);
});
