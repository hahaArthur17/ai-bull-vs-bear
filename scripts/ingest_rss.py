#!/usr/bin/env python3
"""Import RSS evidence as JSON without requiring a third-party SDK.

Example:
    python scripts/ingest_rss.py --ticker AAPL --url https://example.com/feed.xml
"""

from __future__ import annotations

import argparse
import json

from app.services.ingestion import fetch_rss


def main() -> None:
    parser = argparse.ArgumentParser(description="Import an RSS feed into evidence JSON.")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(fetch_rss(args.url, args.ticker, limit=args.limit), indent=2))


if __name__ == "__main__":
    main()
