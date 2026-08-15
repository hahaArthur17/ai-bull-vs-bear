from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import re
from time import monotonic, sleep
from typing import Callable, Iterable

import httpx

from app.services.supabase_headers import service_headers

from app.services.ingestion import fetch_rss
from app.services.rag import build_evidence_chunks


SEC_CIKS = {
    "AAPL": "0000320193",
    "GOOG": "0001652044",
    "NVDA": "0001045810",
    "TSLA": "0001318605",
}

SEC_FINANCIAL_CONCEPTS = {
    "Assets",
    "CashAndCashEquivalentsAtCarryingValue",
    "CommonStockSharesOutstanding",
    "EarningsPerShareDiluted",
    "GrossProfit",
    "Liabilities",
    "NetCashProvidedByUsedInOperatingActivities",
    "NetIncomeLoss",
    "OperatingIncomeLoss",
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "StockholdersEquity",
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
_SEC_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class SecEdgarClient:
    """Small SEC client that follows EDGAR fair-access requirements."""

    def __init__(
        self,
        user_agent: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = 15.0,
        min_interval: float = 0.11,
        max_attempts: int = 3,
        sleeper: Callable[[float], None] = sleep,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("SEC_USER_AGENT must identify the requester and contact email")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.headers = {
            "User-Agent": user_agent.strip(),
            "Accept-Encoding": "gzip, deflate",
        }
        self.client = client
        self.timeout = timeout
        self.min_interval = min_interval
        self.max_attempts = max_attempts
        self.sleeper = sleeper
        self.clock = clock
        self._last_request_at: float | None = None

    def _throttle(self) -> None:
        now = self.clock()
        if self._last_request_at is not None:
            remaining = self.min_interval - (now - self._last_request_at)
            if remaining > 0:
                self.sleeper(remaining)
        self._last_request_at = self.clock()

    def get(self, url: str) -> httpx.Response:
        requester = self.client.get if self.client is not None else httpx.get
        last_error: httpx.RequestError | None = None
        for attempt in range(self.max_attempts):
            self._throttle()
            try:
                response = requester(url, headers=self.headers, timeout=self.timeout)
            except httpx.RequestError as exc:
                last_error = exc
                if attempt + 1 == self.max_attempts:
                    raise
                self.sleeper(0.5 * (2**attempt))
                continue
            if response.status_code in _SEC_RETRY_STATUS_CODES:
                if attempt + 1 == self.max_attempts:
                    response.raise_for_status()
                retry_after = response.headers.get("Retry-After", "")
                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = 0.5 * (2**attempt)
                self.sleeper(max(delay, 0.0))
                continue
            response.raise_for_status()
            return response
        if last_error is not None:
            raise last_error
        raise RuntimeError("SEC request attempts exhausted")


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
                    "content_status": "metadata_only",
                },
            }
        )
    return documents


def fetch_sec_filings(
    ticker: str,
    user_agent: str,
    limit: int = 4,
    timeout: float = 15.0,
    edgar_client: SecEdgarClient | None = None,
) -> list[dict[str, object]]:
    normalized = ticker.upper()
    cik = SEC_CIKS.get(normalized)
    if cik is None:
        raise ValueError(f"Unsupported SEC ticker: {normalized}")
    client = edgar_client or SecEdgarClient(user_agent, timeout=timeout)
    response = client.get(f"https://data.sec.gov/submissions/CIK{cik}.json")
    documents = parse_sec_submissions(response.json(), normalized, limit=limit)
    for document in documents:
        url = document.get("url")
        metadata = document.get("metadata")
        if not isinstance(url, str) or not isinstance(metadata, dict):
            continue
        try:
            filing_response = client.get(url)
        except httpx.HTTPError:
            metadata["filing_fetch_status"] = "unavailable"
            continue
        sections = extract_filing_sections(
            filing_response.text,
            str(metadata.get("form", "")),
        )
        if not sections:
            metadata["filing_fetch_status"] = "no_selected_sections"
            continue
        document["excerpt"] = "\n\n".join(
            f"{section['title']}\n{section['text']}" for section in sections
        )
        metadata.update(
            {
                "source": "SEC EDGAR filing archive",
                "content_status": "selected_sections",
                "filing_fetch_status": "success",
                "sections": [section["title"] for section in sections],
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    return documents


def parse_sec_companyfacts(
    payload: dict[str, object],
    ticker: str,
    limit_per_concept: int = 12,
) -> list[dict[str, object]]:
    """Normalize recent SEC XBRL facts for typed storage and arithmetic."""

    if limit_per_concept < 1:
        raise ValueError("limit_per_concept must be at least 1")
    normalized_ticker = ticker.upper()
    cik = SEC_CIKS[normalized_ticker]
    cik_path = str(int(cik))
    facts_root = payload.get("facts")
    if not isinstance(facts_root, dict):
        return []

    rows: list[dict[str, object]] = []
    seen: set[tuple[str, str, str, str, str, str]] = set()
    for taxonomy in ("us-gaap", "ifrs-full"):
        taxonomy_facts = facts_root.get(taxonomy)
        if not isinstance(taxonomy_facts, dict):
            continue
        for concept, definition in taxonomy_facts.items():
            if concept not in SEC_FINANCIAL_CONCEPTS or not isinstance(definition, dict):
                continue
            units = definition.get("units")
            if not isinstance(units, dict):
                continue
            for unit, observations in units.items():
                if not isinstance(observations, list):
                    continue
                eligible = [
                    observation
                    for observation in observations
                    if isinstance(observation, dict)
                    and observation.get("form") in {"10-K", "10-Q"}
                    and observation.get("end")
                    and observation.get("filed")
                    and observation.get("accn")
                    and isinstance(observation.get("val"), (int, float))
                    and not isinstance(observation.get("val"), bool)
                ]
                eligible.sort(
                    key=lambda item: (
                        str(item.get("filed", "")),
                        str(item.get("end", "")),
                    ),
                    reverse=True,
                )
                for observation in eligible[:limit_per_concept]:
                    period_end = str(observation["end"])
                    period_start = str(observation.get("start") or period_end)
                    accession = str(observation["accn"])
                    identity = (
                        taxonomy,
                        str(concept),
                        str(unit),
                        period_start,
                        period_end,
                        accession,
                    )
                    if identity in seen:
                        continue
                    seen.add(identity)
                    fiscal_year = observation.get("fy")
                    compact_accession = accession.replace("-", "")
                    rows.append(
                        {
                            "ticker": normalized_ticker,
                            "taxonomy": taxonomy,
                            "concept": str(concept),
                            "label": str(definition.get("label") or concept),
                            "description": str(definition.get("description") or "") or None,
                            "unit": str(unit),
                            "value": observation["val"],
                            "period_start": period_start,
                            "period_end": period_end,
                            "fiscal_year": (
                                int(fiscal_year)
                                if isinstance(fiscal_year, (int, float, str))
                                and str(fiscal_year).isdigit()
                                else None
                            ),
                            "fiscal_period": str(observation.get("fp") or "") or None,
                            "form": str(observation["form"]),
                            "filed_at": str(observation["filed"]),
                            "accession_number": accession,
                            "frame": str(observation.get("frame") or "") or None,
                            "source_url": (
                                "https://www.sec.gov/Archives/edgar/data/"
                                f"{cik_path}/{compact_accession}/"
                            ),
                            "metadata": {
                                "source": "SEC EDGAR companyfacts API",
                                "entity_name": str(payload.get("entityName") or ""),
                            },
                        }
                    )
    return rows


def fetch_sec_companyfacts(
    ticker: str,
    user_agent: str,
    limit_per_concept: int = 12,
    timeout: float = 15.0,
    edgar_client: SecEdgarClient | None = None,
) -> list[dict[str, object]]:
    normalized = ticker.upper()
    cik = SEC_CIKS.get(normalized)
    if cik is None:
        raise ValueError(f"Unsupported SEC ticker: {normalized}")
    client = edgar_client or SecEdgarClient(user_agent, timeout=timeout)
    response = client.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
    return parse_sec_companyfacts(
        response.json(),
        normalized,
        limit_per_concept=limit_per_concept,
    )


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
        self._stock_ids: dict[str, int] = {}

    def _headers(self, prefer: str) -> dict[str, str]:
        return service_headers(self.secret_key, prefer)

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
        normalized = ticker.upper()
        if normalized in self._stock_ids:
            return self._stock_ids[normalized]
        response = self._request(
            "GET",
            "stocks",
            params={"select": "id", "ticker": f"eq.{normalized}", "limit": "1"},
        )
        rows = response.json()
        if not rows:
            raise RuntimeError(f"Stock {normalized} is not seeded")
        self._stock_ids[normalized] = int(rows[0]["id"])
        return self._stock_ids[normalized]

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
                self._replace_chunks(int(document_rows[0]["id"]), document, metadata)
            written += 1
        return written

    def upsert_financial_facts(self, facts: Iterable[dict[str, object]]) -> int:
        payloads: list[dict[str, object]] = []
        for fact in facts:
            payloads.append(
                {
                    "stock_id": self.stock_id(str(fact["ticker"])),
                    "taxonomy": fact["taxonomy"],
                    "concept": fact["concept"],
                    "label": fact["label"],
                    "description": fact.get("description"),
                    "unit": fact["unit"],
                    "value": fact["value"],
                    "period_start": fact["period_start"],
                    "period_end": fact["period_end"],
                    "fiscal_year": fact.get("fiscal_year"),
                    "fiscal_period": fact.get("fiscal_period"),
                    "form": fact["form"],
                    "filed_at": fact["filed_at"],
                    "accession_number": fact["accession_number"],
                    "frame": fact.get("frame"),
                    "source_url": fact["source_url"],
                    "metadata": fact.get("metadata") or {},
                }
            )
        if payloads:
            self._request(
                "POST",
                "financial_facts",
                params={
                    "on_conflict": (
                        "stock_id,taxonomy,concept,unit,period_start,period_end,"
                        "accession_number"
                    )
                },
                json=payloads,
                prefer="resolution=merge-duplicates,return=minimal",
            )
        return len(payloads)

    def _replace_chunks(
        self,
        document_id: int,
        document: dict[str, object],
        metadata: dict[str, object],
    ) -> None:
        self._request(
            "DELETE",
            "evidence_chunks",
            params={"document_id": f"eq.{document_id}"},
            prefer="return=minimal",
        )
        prepared_chunks = build_evidence_chunks(
            text=str(document["excerpt"]),
            title=str(document["title"]),
            ticker=str(document["ticker"]),
            source_type=str(document["source_type"]),
            published_at=str(document.get("published_at") or "") or None,
            metadata=metadata,
        )
        chunks = [
            {
                "document_id": document_id,
                "chunk_text": prepared["chunk_text"],
                "metadata": {
                    **metadata,
                    **prepared["metadata"],
                    "chunk_index": index,
                    "parent_external_id": str(document["id"]),
                },
            }
            for index, prepared in enumerate(prepared_chunks, start=1)
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
    xbrl_count = 0
    edgar_client = SecEdgarClient(sec_user_agent)
    for ticker in SEC_CIKS:
        sec_count += writer.upsert_documents(
            fetch_sec_filings(
                ticker,
                sec_user_agent,
                limit=per_source_limit,
                edgar_client=edgar_client,
            )
        )
        xbrl_count += writer.upsert_financial_facts(
            fetch_sec_companyfacts(
                ticker,
                sec_user_agent,
                edgar_client=edgar_client,
            )
        )
    return {"rss": rss_count, "sec": sec_count, "xbrl": xbrl_count}
