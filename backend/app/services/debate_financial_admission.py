"""Bounded SEC financial observations; never infer ratios across periods."""
from datetime import date, datetime
import re
from urllib.parse import urlsplit

from app.domain.factors import AnalysisFinancialFact


class LiveFinancialFactsUnavailable(ValueError):
    pass


def select_live_financial_facts(ticker: str, rows: list[dict[str, object]], *,
                                captured_at: datetime, cik: int | None) -> list[AnalysisFinancialFact]:
    if not cik or captured_at.tzinfo is None:
        raise LiveFinancialFactsUnavailable("Live Debate requires SEC financial provenance")
    eligible = {}
    for row in rows:
        try:
            fact = AnalysisFinancialFact.model_validate(row)
            start, end, filed = (date.fromisoformat(value) for value in
                                 (fact.period_start, fact.period_end, fact.filed_at))
            source = urlsplit(fact.source_url)
            accession = fact.accession_number
            prefix = f"/Archives/edgar/data/{cik}/{accession.replace('-', '')}/"
            if (fact.ticker != ticker.upper() or fact.form not in {"10-K", "10-Q"}
                    or fact.taxonomy not in {"us-gaap", "ifrs-full"}
                    or fact.metadata.get("storage") != "supabase"
                    or not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession)
                    or source.scheme != "https" or source.hostname not in {"www.sec.gov", "sec.gov"}
                    or source.username or source.password or not source.path.startswith(prefix)
                    or not start <= end <= filed <= captured_at.date()
                    or (captured_at.date() - filed).days > 120
                    or (captured_at.date() - end).days > 450):
                continue
        except (ValueError, TypeError):
            continue
        key = (fact.taxonomy, fact.concept, fact.unit, fact.period_start, fact.period_end)
        previous = eligible.get(key)
        if previous and previous.filed_at == fact.filed_at and previous.value != fact.value:
            raise LiveFinancialFactsUnavailable("Conflicting financial facts require review")
        if previous is None or (fact.filed_at, fact.accession_number) > (previous.filed_at, previous.accession_number):
            eligible[key] = fact
    if not eligible:
        raise LiveFinancialFactsUnavailable("Live Debate requires recent verified SEC financial facts")
    return sorted(eligible.values(), key=lambda f: (f.period_end, f.filed_at, f.id), reverse=True)[:32]
