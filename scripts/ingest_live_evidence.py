#!/usr/bin/env python3
from __future__ import annotations

import json

from app.config import get_settings
from app.services.evidence_ingestion import EvidenceWriter, ingest_live_evidence


def main() -> None:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
    if not settings.sec_user_agent:
        raise SystemExit("SEC_USER_AGENT must identify the project and a contact email")
    writer = EvidenceWriter(settings.supabase_url, settings.supabase_secret_key)
    print(
        json.dumps(
            ingest_live_evidence(
                writer,
                settings.sec_user_agent,
                tickers=settings.live_evidence_ticker_list,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
