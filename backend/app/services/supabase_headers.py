from __future__ import annotations


def service_headers(api_key: str, prefer: str) -> dict[str, str]:
    """Build REST headers for current and legacy Supabase server keys."""

    headers = {
        "apikey": api_key,
        "Content-Type": "application/json",
        "Prefer": prefer,
    }
    if not api_key.startswith("sb_"):
        headers["Authorization"] = f"Bearer {api_key}"
    return headers
