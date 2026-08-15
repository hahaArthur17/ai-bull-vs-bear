import httpx

from app.services.evidence_ingestion import (
    SecEdgarClient,
    extract_filing_sections,
    fetch_sec_companyfacts,
    fetch_sec_filings,
    parse_sec_companyfacts,
    parse_sec_submissions,
)


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
    assert documents[0]["metadata"]["content_status"] == "metadata_only"


def test_extract_filing_sections_prefers_full_sections_over_table_of_contents() -> None:
    filing_html = """
    <html><body>
      <div>Item 1A. Risk Factors</div><div>Item 1B. Unresolved Staff Comments</div>
      <h2>Item 1A. Risk Factors</h2>
      <p>Our operations face supply constraints, changing customer demand, and
      regulatory uncertainty. These risks may affect revenue, margins, product
      availability, and the timing of planned investments across markets.</p>
      <h2>Item 1B. Unresolved Staff Comments</h2>
      <h2>Item 7. Management's Discussion and Analysis</h2>
      <p>Revenue increased during the period while operating costs also rose.
      Management evaluates liquidity, capital spending, and demand using both
      current results and longer-term business conditions.</p>
      <h2>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</h2>
    </body></html>
    """

    sections = extract_filing_sections(filing_html, "10-K")

    assert [section["title"] for section in sections] == [
        "Item 1A — Risk Factors",
        "Item 7 — Management's Discussion and Analysis",
    ]
    assert "supply constraints" in sections[0]["text"]
    assert "Revenue increased" in sections[1]["text"]


def test_extract_filing_sections_ignores_hidden_inline_xbrl_content() -> None:
    filing_html = """
    <html><body>
      <ix:hidden>Item 1A. Risk Factors hidden duplicate Item 2.</ix:hidden>
      <h2>Item 1A. Risk Factors</h2>
      <p>The quarterly filing describes material cybersecurity, competition,
      supply, and execution risks in enough detail for retrieval and citation.</p>
      <h2>Item 2. Unregistered Sales of Equity Securities</h2>
    </body></html>
    """

    sections = extract_filing_sections(filing_html, "10-Q")

    assert sections == [
        {
            "title": "Item 1A — Risk Factors",
            "text": (
                "The quarterly filing describes material cybersecurity, competition, "
                "supply, and execution risks in enough detail for retrieval and citation."
            ),
        }
    ]


def test_sec_client_declares_identity_and_retries_rate_limit() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        assert request.headers["user-agent"] == "AI Bull vs Bear admin@example.com"
        assert request.headers["accept-encoding"] == "gzip, deflate"
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "1.25"})
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = SecEdgarClient(
        "AI Bull vs Bear admin@example.com",
        client=httpx.Client(transport=transport),
        min_interval=0,
        sleeper=delays.append,
    )

    response = client.get("https://data.sec.gov/submissions/example.json")

    assert response.json() == {"ok": True}
    assert attempts == 2
    assert delays == [1.25]


def test_sec_client_rejects_empty_user_agent() -> None:
    try:
        SecEdgarClient("   ")
    except ValueError as exc:
        assert "SEC_USER_AGENT" in str(exc)
    else:
        raise AssertionError("Expected an empty SEC user agent to be rejected")


def test_fetch_sec_filings_attaches_selected_section_text() -> None:
    submissions = {
        "filings": {
            "recent": {
                "form": ["10-K"],
                "accessionNumber": ["000000-26-000003"],
                "primaryDocument": ["annual.htm"],
                "filingDate": ["2026-03-01"],
                "reportDate": ["2025-12-31"],
            }
        }
    }
    filing_html = """
    <html><body>
      <h2>Item 1A. Risk Factors</h2>
      <p>The company faces changing demand, supply constraints, cybersecurity
      events, and regulatory requirements that may materially affect results.</p>
      <h2>Item 1B. Unresolved Staff Comments</h2>
    </body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "data.sec.gov":
            return httpx.Response(200, json=submissions)
        return httpx.Response(200, text=filing_html)

    transport = httpx.MockTransport(handler)
    client = SecEdgarClient(
        "AI Bull vs Bear admin@example.com",
        client=httpx.Client(transport=transport),
        min_interval=0,
    )

    documents = fetch_sec_filings(
        "AAPL",
        "AI Bull vs Bear admin@example.com",
        limit=1,
        edgar_client=client,
    )

    assert "supply constraints" in documents[0]["excerpt"]
    assert documents[0]["metadata"]["content_status"] == "selected_sections"
    assert documents[0]["metadata"]["sections"] == ["Item 1A — Risk Factors"]


def test_fetch_sec_filings_keeps_metadata_when_filing_is_unavailable() -> None:
    submissions = {
        "filings": {
            "recent": {
                "form": ["10-Q"],
                "accessionNumber": ["000000-26-000002"],
                "primaryDocument": ["quarter.htm"],
                "filingDate": ["2026-02-01"],
                "reportDate": ["2025-12-31"],
            }
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "data.sec.gov":
            return httpx.Response(200, json=submissions)
        return httpx.Response(503)

    transport = httpx.MockTransport(handler)
    client = SecEdgarClient(
        "AI Bull vs Bear admin@example.com",
        client=httpx.Client(transport=transport),
        min_interval=0,
        max_attempts=1,
    )

    documents = fetch_sec_filings(
        "AAPL",
        "AI Bull vs Bear admin@example.com",
        limit=1,
        edgar_client=client,
    )

    assert documents[0]["metadata"]["content_status"] == "metadata_only"
    assert documents[0]["metadata"]["filing_fetch_status"] == "unavailable"


def test_parse_sec_companyfacts_preserves_period_units_and_provenance() -> None:
    payload = {
        "entityName": "Example Corp",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "label": "Revenue",
                    "description": "Revenue from customers.",
                    "units": {
                        "USD": [
                            {
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "val": 125000000,
                                "accn": "0000320193-26-000001",
                                "fy": 2026,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-05-01",
                                "frame": "CY2026Q1",
                            },
                            {
                                "end": "2026-03-31",
                                "val": 999,
                                "accn": "0000320193-26-000002",
                                "form": "8-K",
                                "filed": "2026-05-02",
                            },
                        ]
                    },
                },
                "UnselectedConcept": {
                    "label": "Ignored",
                    "units": {"USD": []},
                },
            }
        },
    }

    facts = parse_sec_companyfacts(payload, "AAPL")

    assert len(facts) == 1
    assert facts[0]["concept"] == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert facts[0]["unit"] == "USD"
    assert facts[0]["period_start"] == "2026-01-01"
    assert facts[0]["period_end"] == "2026-03-31"
    assert facts[0]["fiscal_period"] == "Q1"
    assert facts[0]["source_url"].endswith("/320193/000032019326000001/")


def test_fetch_sec_companyfacts_uses_companyfacts_endpoint() -> None:
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, json={"facts": {}})

    client = SecEdgarClient(
        "AI Bull vs Bear admin@example.com",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        min_interval=0,
    )

    facts = fetch_sec_companyfacts(
        "NVDA",
        "AI Bull vs Bear admin@example.com",
        edgar_client=client,
    )

    assert facts == []
    assert requested_urls == [
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json"
    ]
