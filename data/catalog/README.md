# Versioned stock catalog

This directory contains generated, reviewable stock-identity snapshots. The
application must not update these files during startup or a user search.

## Current snapshot

`sec-company-tickers-exchange-2026-08-27.json` was generated from the SEC
`company_tickers_exchange.json` file retrieved on 2026-08-27.

- Raw rows: 10,388
- Included Nasdaq, NYSE, and CBOE rows: 7,695
- Excluded OTC or missing-exchange rows: 2,693
- Raw source SHA-256:
  `ab3f22c4c6549d7e3eadfe5ff5420bfff654ea4e4f2c7ea7e96382ea2a98b422`
- Transformation: `sec-exchange-v1`

The snapshot contains issuer identity only. It is not evidence of current
price, evidence, sector, country, or Debate coverage.

## Refresh procedure

1. Download the official
   [`company_tickers_exchange.json`](https://www.sec.gov/files/company_tickers_exchange.json)
   once with a declared `SEC_USER_AGENT`, following the
   [SEC fair-access guidance](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).
2. Review the downloaded JSON before processing it.
3. Generate a new dated file without overwriting the previous snapshot:

   ```shell
   PYTHONPATH=backend backend/.venv/bin/python scripts/build_stock_catalog.py \
     --input /reviewed/path/company_tickers_exchange.json \
     --retrieved-on YYYY-MM-DD \
     --output data/catalog/sec-company-tickers-exchange-YYYY-MM-DD.json
   ```

4. Run `backend/tests/test_stock_catalog.py`, update its expected provenance,
   and review the row-count difference before committing.
5. Generate the matching Supabase seed as a separate dated migration:

   ```shell
   PYTHONPATH=backend backend/.venv/bin/python scripts/build_stock_catalog_seed.py \
     --input data/catalog/sec-company-tickers-exchange-YYYY-MM-DD.json \
     --output backend/supabase/migrations/YYYYMMDD_stock_catalog_seed.sql
   ```

6. Run `backend/tests/test_stock_catalog_seed.py`. It verifies that the checked-in
   SQL exactly matches the reviewed snapshot. A refresh must never silently
   promote or downgrade a stock's coverage status.
