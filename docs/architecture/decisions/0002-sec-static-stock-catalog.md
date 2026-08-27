# ADR-0002: Use a Versioned SEC Snapshot for the Stock Catalog

Date: 2026-08-27

Status: Accepted

## Context

The current application loads four Debate-ready stocks from `DemoStore`.
`SupabaseStore` inherits that list, so `GET /stocks?q=...` cannot identify a
stock outside AAPL, GOOG, NVDA, and TSLA even when the hosted `stocks` table
contains more rows.

Search must remain useful on the free deployment without spending quote,
fundamental-data, news, or model-provider quota. The catalog also needs a stable
issuer identifier for later SEC evidence ingestion, but a catalog match must not
imply that price or Debate data is available.

The SEC publishes
[`company_tickers_exchange.json`](https://www.sec.gov/files/company_tickers_exchange.json)
with CIK, EDGAR-conformed company name, ticker, and exchange associations. Its
[EDGAR access documentation](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
states that the mapping is updated periodically but does not guarantee its
accuracy or scope. The SEC also states that Government-created site content and
public EDGAR content are
[free to access and reuse](https://www.sec.gov/about/webmaster-frequently-asked-questions).

## Decision

Use a checked-in, versioned snapshot derived from the SEC exchange-association
file as the Phase 2 catalog source.

- Downloading and normalization happen only through an explicit maintenance
  command, never in a user request or normal application startup.
- Record the source URL, retrieval date, transformation version, row count, and
  snapshot checksum with the generated catalog.
- Accept rows whose exchange is `Nasdaq`, `NYSE`, or `CBOE`; exclude OTC and
  rows without an exchange from the initial classroom catalog.
- Enforce a hard maximum of 10,000 normalized rows so a changed upstream file
  cannot create an unbounded migration or repository payload.
- Preserve `sec_cik`, ticker, EDGAR company name, and exchange. Tickers are
  normalized to uppercase and duplicates are rejected during generation.
- Treat the result as a US-exchange catalog, not a list of US-incorporated
  companies. `country` remains unknown unless a separate verified source is
  added later.
- Do not infer sector from an issuer name. Existing curated sectors for the four
  Debate-ready stocks remain; catalog-only rows may have no sector.
- A small reviewed alias override can cover common class-symbol or company-name
  searches. Generated search text is deterministic and contains only normalized
  ticker, company name, and reviewed aliases.
- A catalog import never changes the four existing symbols from
  `debate_ready`. All other imported rows start as `catalog_only`.

The application reads the checked-in catalog or Supabase rows at runtime. Stock
search therefore performs zero SEC, market-data, news, or model-provider calls.

## Rejected alternatives

### Search a market-data provider on demand

This consumes free quota, makes search availability depend on a third party,
and mixes stock identity with paid/live coverage.

### Query the SEC from each search request

The SEC file is suitable for periodic catalog maintenance, not type-ahead
traffic. Runtime calls would add latency, fair-access obligations, and an
avoidable external dependency.

### Use an index constituent list

An index list is smaller, but it introduces separate licensing/provenance work
and excludes many valid exchange-listed companies. It also changes for reasons
unrelated to whether a ticker can be identified.

### Label every SEC row as a US company with complete metadata

The selected file includes foreign issuers trading on US exchanges and does not
provide country or sector. Inferring those fields would create misleading data.

## Consequences

- The catalog can be committed and seeded into Supabase without a runtime API
  key or recurring free-tier request cost.
- `stocks.sector` must become nullable for catalog-only rows.
- Phase 2 adds nullable `sec_cik` and country/alias fields plus explicit coverage
  metadata; CIK is not unique because one issuer can have multiple share-class
  tickers.
- The generated snapshot and transformation tests become reviewable portfolio
  evidence.
- A periodic manual refresh is required. The UI must not claim that the catalog
  is complete or real-time.
- Search results identify securities only. Price, evidence, and Debate endpoints
  must continue to enforce their own coverage requirements.

## Implementation gate

Before the Phase 2 migration is accepted:

1. validate the snapshot schema, supported exchanges, maximum size, and unique
   normalized ticker;
2. prove the four existing tickers retain their curated metadata and
   `debate_ready` status;
3. seed at least one `catalog_only` ticker used by API and RLS tests;
4. prove `GET /stocks?q=...` uses no market-data or external catalog client; and
5. document the exact snapshot retrieval date and checksum.
