#!/usr/bin/env python3
"""Build a deterministic stock catalog from one reviewed SEC download."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from app.services.stock_catalog import CatalogSnapshotError, build_catalog_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize a local SEC ticker/exchange JSON file into a versioned catalog."
    )
    parser.add_argument("--input", type=Path, required=True, help="Reviewed SEC JSON download")
    parser.add_argument("--retrieved-on", required=True, help="Download date in YYYY-MM-DD form")
    parser.add_argument("--output", type=Path, required=True, help="Snapshot JSON destination")
    args = parser.parse_args()

    try:
        source_bytes = args.input.read_bytes()
        payload = json.loads(source_bytes)
        snapshot = build_catalog_snapshot(
            payload,
            retrieved_on=args.retrieved_on,
            source_sha256=sha256(source_bytes).hexdigest(),
        )
    except (CatalogSnapshotError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Catalog generation failed: {exc}") from exc

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(snapshot['stocks'])} catalog rows to {args.output}")


if __name__ == "__main__":
    main()
