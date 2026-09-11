from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Awaitable, Callable


class ProviderRequestPacer:
    """Serialize provider request starts behind a monotonic minimum interval."""

    def __init__(
        self,
        min_interval_seconds: float = 0,
        *,
        monotonic: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        if (
            not math.isfinite(min_interval_seconds)
            or min_interval_seconds < 0
        ):
            raise ValueError("Provider request interval must be finite and non-negative")
        self.min_interval_seconds = min_interval_seconds
        self._monotonic = monotonic or time.monotonic
        self._sleep = sleep or asyncio.sleep
        self._lock = asyncio.Lock()
        self._last_started_at: float | None = None

    async def wait(self) -> None:
        async with self._lock:
            now = self._monotonic()
            if self._last_started_at is not None:
                remaining = self.min_interval_seconds - (now - self._last_started_at)
                if remaining > 0:
                    await self._sleep(remaining)
            self._last_started_at = self._monotonic()
