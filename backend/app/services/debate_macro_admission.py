"""Application eligibility policy for the seven cached daily macro series."""
from datetime import date, datetime

from app.domain.factors import AnalysisMacroObservation
from app.services.macro_data import DEFAULT_MACRO_SERIES


# Calendar-day limits tolerate weekends and short publication delays. These
# are application policy, not assertions about a provider's publication SLA.
MACRO_MAX_AGE_DAYS = {item.code: 7 for item in DEFAULT_MACRO_SERIES}


class LiveMacroUnavailable(ValueError):
    pass


def require_live_macro_context(rows: list[dict[str, object]], *, captured_at: datetime,
                               completed_through: str) -> list[dict[str, object]]:
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise LiveMacroUnavailable("Live macro capture requires a timezone")
    expected = {item.code: item for item in DEFAULT_MACRO_SERIES}
    selected = {}
    try:
        cutoff = date.fromisoformat(completed_through)
        for row in rows:
            item = AnalysisMacroObservation.model_validate(row)
            if item.code not in expected:
                continue
            definition = expected[item.code]
            observed = date.fromisoformat(item.observation_date)
            retrieved = datetime.fromisoformat(item.retrieved_at.replace("Z", "+00:00"))
            max_age = MACRO_MAX_AGE_DAYS[item.code]
            if (item.code in selected or item.source != definition.source
                    or item.unit != definition.unit
                    or item.metadata.get("provider") != definition.source
                    or item.metadata.get("provider_series_id") != definition.provider_series_id
                    or retrieved.tzinfo is None or retrieved.utcoffset() is None
                    or not observed <= cutoff <= captured_at.date()
                    or not observed <= retrieved.date() <= captured_at.date()
                    or retrieved > captured_at
                    or (captured_at.date() - observed).days > max_age
                    or (captured_at - retrieved).total_seconds() > max_age * 86400):
                raise ValueError("Ineligible macro observation")
            selected[item.code] = item.model_dump(mode="python")
        if set(selected) != set(expected):
            raise ValueError("Missing required macro series")
    except (ValueError, TypeError) as exc:
        raise LiveMacroUnavailable("Live Debate requires all seven current verified macro series") from exc
    return [selected[definition.code] for definition in DEFAULT_MACRO_SERIES]
