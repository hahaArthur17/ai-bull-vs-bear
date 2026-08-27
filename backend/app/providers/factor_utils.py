from __future__ import annotations

import re
from hashlib import sha1


def factor_key_segment(value: str, *, max_length: int = 48) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "unknown"
    if not normalized[0].isalpha():
        normalized = f"x-{normalized}"
    if len(normalized) <= max_length:
        return normalized
    digest = sha1(normalized.encode("utf-8")).hexdigest()[:8]
    return f"{normalized[: max_length - 9]}-{digest}"


def factor_observation_id(provider: str, *parts: str) -> str:
    raw = ":".join((provider, *parts))
    if len(raw) <= 240:
        return raw
    digest = sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{raw[:227]}:{digest}"

