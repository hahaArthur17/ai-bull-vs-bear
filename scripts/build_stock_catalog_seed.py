#!/usr/bin/env python3
"""Render an idempotent Supabase seed from a reviewed catalog snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.stock_catalog_seed import CatalogSeedError, render_catalog_seed_sql


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render a Supabase stock seed from a versioned catalog snapshot."
    )
    parser.add_argument("--input", type=Path, required=True, help="Catalog snapshot JSON")
    parser.add_argument("--output", type=Path, required=True, help="SQL migration destination")
    args = parser.parse_args()

    try:
        snapshot = json.loads(args.input.read_text(encoding="utf-8"))
        sql = render_catalog_seed_sql(snapshot)
    except (CatalogSeedError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Catalog seed generation failed: {exc}") from exc

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(sql, encoding="utf-8")
    print(f"Wrote catalog seed SQL to {args.output}")


if __name__ == "__main__":
    main()
