import httpx

from app.services.evidence_ingestion import (
    SecEdgarClient,
    extract_filing_sections,
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
