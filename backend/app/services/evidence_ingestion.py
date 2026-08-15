from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import re
from time import sleep
from typing import Iterable

import httpx

from app.services.ingestion import fetch_rss
from app.services.rag import chunk_text


SEC_CIKS = {
    "AAPL": "0000320193",
    "GOOG": "0001652044",
    "NVDA": "0001045810",
    "TSLA": "0001318605",
}

_SECTION_SPECS = {
    "10-K": (
        (
            "Item 1A — Risk Factors",
            r"\bitem\s+1a\s*[.:-—]*\s*risk\s+factors\b",
            r"\bitem\s+1b\b",
        ),
        (
            "Item 7 — Management's Discussion and Analysis",
            r"\bitem\s+7\s*[.:-—]*\s*management(?:['’]s)?\s+discussion\s+and\s+analysis\b",
            r"\bitem\s+7a\b",
        ),
    ),
    "10-Q": (
        (
            "Item 2 — Management's Discussion and Analysis",
            r"\bitem\s+2\s*[.:-—]*\s*management(?:['’]s)?\s+discussion\s+and\s+analysis\b",
            r"\bitem\s+3\b",
        ),
        (
            "Item 1A — Risk Factors",
            r"\bitem\s+1a\s*[.:-—]*\s*risk\s+factors\b",
            r"\bitem\s+2\b",
        ),
    ),
}


class _FilingTextParser(HTMLParser):
    _BLOCK_TAGS = {
        "article",
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "p",
        "section",
        "table",
        "td",
        "th",
        "tr",
    }
    _IGNORED_TAGS = {"ix:hidden", "noscript", "script", "style", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        if normalized in self._IGNORED_TAGS:
            self.ignored_depth += 1
        elif self.ignored_depth == 0 and normalized in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in self._IGNORED_TAGS and self.ignored_depth:
            self.ignored_depth -= 1
        elif self.ignored_depth == 0 and normalized in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.ignored_depth == 0:
            self.parts.append(data)

    def text(self) -> str:
        lines = (
            re.sub(r"\s+", " ", line).strip()
            for line in "".join(self.parts).splitlines()
        )
        return "\n".join(line for line in lines if line)


def _extract_longest_section(
    text: str,
    start_pattern: str,
    end_pattern: str,
    max_chars: int,
) -> str | None:
    candidates: list[str] = []
    for start in re.finditer(start_pattern, text, flags=re.IGNORECASE):
        end = re.search(end_pattern, text[start.end() :], flags=re.IGNORECASE)
        if end is None:
            continue
        content = re.sub(
            r"\s+",
            " ",
            text[start.end() : start.end() + end.start()],
        ).strip(" \n:-")
        if len(content) >= 80:
            candidates.append(content)
    if not candidates:
        return None
    longest = max(candidates, key=len)
    if len(longest) <= max_chars:
        return longest
    truncated = longest[:max_chars].rsplit(" ", 1)[0].rstrip(" ,.;:")
    return f"{truncated} …"


def extract_filing_sections(
    filing_html: str,
    form: str,
    max_chars_per_section: int = 8_000,
) -> list[dict[str, str]]:
    """Extract useful narrative sections from a 10-K or 10-Q filing."""

    parser = _FilingTextParser()
    parser.feed(filing_html)
    text = parser.text()
    sections: list[dict[str, str]] = []
    for title, start_pattern, end_pattern in _SECTION_SPECS.get(form.upper(), ()):
        content = _extract_longest_section(
            text,
            start_pattern,
            end_pattern,
            max_chars=max_chars_per_section,
        )
        if content:
            sections.append({"title": title, "text": content})
    return sections


def parse_sec_submissions(
    payload: dict[str, object],
    ticker: str,
    limit: int = 4,
) -> list[dict[str, object]]:
    filings = payload.get("filings", {})
    recent = filings.get("recent", {}) if isinstance(filings, dict) else {}
    if not isinstance(recent, dict):
        return []
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    primary_documents = recent.get("primaryDocument", [])
    filing_dates = recent.get("filingDate", [])
    reports = recent.get("reportDate", [])
    documents: list[dict[str, object]] = []
    cik = SEC_CIKS[ticker.upper()]
    cik_path = str(int(cik))
    for index, form in enumerate(forms if isinstance(forms, list) else []):
        if form not in {"10-K", "10-Q"} or len(documents) >= limit:
            continue
        accession = str(accessions[index])
        primary_document = str(primary_documents[index])
        compact_accession = accession.replace("-", "")
        filing_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik_path}/"
            f"{compact_accession}/{primary_document}"
        )
        filing_date = str(filing_dates[index])
        report_date = str(reports[index]) if index < len(reports) else ""
        documents.append(
            {
                "id": f"sec-{ticker.lower()}-{accession}",
                "ticker": ticker.upper(),
                "source_type": "filing",
                "title": f"{ticker.upper()} {form} filed {filing_date}",
                "url": filing_url,
                "published_at": filing_date,
                "excerpt": (
                    f"SEC EDGAR metadata for {form}, reporting period {report_date or 'not supplied'}. "
                    "Open the source filing for the complete disclosures and risk factors."
                ),
                "metadata": {
                    "source": "SEC EDGAR submissions API",
                    "form": str(form),
                    "accession_number": accession,
                    "report_date": report_date,
                    "cik": cik,
                },
            }
        )
    return documents


def fetch_sec_filings(
    ticker: str,
    user_agent: str,
    limit: int = 4,
    timeout: float = 15.0,
) -> list[dict[str, object]]:
    normalized = ticker.upper()
    cik = SEC_CIKS.get(normalized)
    if cik is None:
        raise ValueError(f"Unsupported SEC ticker: {normalized}")
    response = httpx.get(
        f"https://data.sec.gov/submissions/CIK{cik}.json",
        headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
        timeout=timeout,
    )
    response.raise_for_status()
    return parse_sec_submissions(response.json(), normalized, limit=limit)


class EvidenceWriter:
    def __init__(
        self,
        supabase_url: str,
        secret_key: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.rest_url = f"{supabase_url.rstrip('/')}/rest/v1"
        self.secret_key = secret_key
        self.client = client

    def _headers(self, prefer: str) -> dict[str, str]:
        return {
            "apikey": self.secret_key,
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        }

    def _request(self, method: str, table: str, **kwargs: object) -> httpx.Response:
        requester = self.client.request if self.client is not None else httpx.request
        response = requester(
            method,
            f"{self.rest_url}/{table}",
            headers=self._headers(str(kwargs.pop("prefer", "return=representation"))),
            timeout=15.0,
            **kwargs,
        )
        response.raise_for_status()
        return response

    def stock_id(self, ticker: str) -> int:
        response = self._request(
            "GET",
            "stocks",
            params={"select": "id", "ticker": f"eq.{ticker.upper()}", "limit": "1"},
        )
        rows = response.json()
        if not rows:
            raise RuntimeError(f"Stock {ticker.upper()} is not seeded")
        return int(rows[0]["id"])

    def upsert_documents(self, documents: Iterable[dict[str, object]]) -> int:
        written = 0
        ingestion_time = datetime.now(timezone.utc).isoformat()
        for document in documents:
            ticker = str(document["ticker"])
            raw_metadata = document.get("metadata")
            metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
            metadata["ingested_at"] = ingestion_time
            payload = {
                "stock_id": self.stock_id(ticker),
                "source_type": document["source_type"],
                "external_id": document["id"],
                "title": document["title"],
                "url": document.get("url"),
                "published_at": document.get("published_at") or None,
                "raw_text": document["excerpt"],
                "metadata": metadata,
            }
            self._request(
                "POST",
                "evidence_documents",
                params={"on_conflict": "external_id"},
                json=payload,
                prefer="resolution=merge-duplicates,return=representation",
            )
            document_response = self._request(
                "GET",
                "evidence_documents",
                params={"select": "id", "external_id": f"eq.{document['id']}", "limit": "1"},
            )
            document_rows = document_response.json()
            if document_rows:
                self._replace_chunks(int(document_rows[0]["id"]), str(document["excerpt"]), metadata)
            written += 1
        return written

    def _replace_chunks(
        self,
        document_id: int,
        text: str,
        metadata: dict[str, object],
    ) -> None:
        self._request(
            "DELETE",
            "evidence_chunks",
            params={"document_id": f"eq.{document_id}"},
            prefer="return=minimal",
        )
        chunks = [
            {
                "document_id": document_id,
                "chunk_text": chunk,
                "metadata": {**metadata, "chunk_index": str(index)},
            }
            for index, chunk in enumerate(chunk_text(text), start=1)
        ]
        if chunks:
            self._request(
                "POST",
                "evidence_chunks",
                json=chunks,
                prefer="return=minimal",
            )


def ingest_live_evidence(
    writer: EvidenceWriter,
    sec_user_agent: str,
    rss_feeds: dict[str, str] | None = None,
    per_source_limit: int = 4,
) -> dict[str, int]:
    feeds = rss_feeds or {
        "NVDA": "https://nvidianews.nvidia.com/releases.xml",
    }
    rss_count = 0
    for ticker, url in feeds.items():
        rss_count += writer.upsert_documents(fetch_rss(url, ticker, limit=per_source_limit))
    sec_count = 0
    for ticker in SEC_CIKS:
        sec_count += writer.upsert_documents(
            fetch_sec_filings(ticker, sec_user_agent, limit=per_source_limit)
        )
        sleep(0.11)
    return {"rss": rss_count, "sec": sec_count}
