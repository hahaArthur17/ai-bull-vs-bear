from app.services.evidence_ingestion import parse_sec_submissions


def test_parse_sec_submissions_selects_periodic_filings() -> None:
    payload = {
        "filings": {
            "recent": {
                "form": ["8-K", "10-Q", "10-K"],
                "accessionNumber": ["000000-26-000001", "000000-26-000002", "000000-26-000003"],
                "primaryDocument": ["current.htm", "quarter.htm", "annual.htm"],
                "filingDate": ["2026-01-01", "2026-02-01", "2026-03-01"],
                "reportDate": ["2025-12-20", "2025-12-31", "2025-12-31"],
            }
        }
    }

    documents = parse_sec_submissions(payload, "AAPL")

    assert [item["metadata"]["form"] for item in documents] == ["10-Q", "10-K"]
    assert documents[0]["url"].startswith("https://www.sec.gov/Archives/edgar/data/320193/")
    assert documents[0]["id"] == "sec-aapl-000000-26-000002"
