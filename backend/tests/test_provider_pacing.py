from __future__ import annotations

import asyncio
import math

import pytest

from app.services.provider_pacing import ProviderRequestPacer


def test_provider_pacer_waits_from_the_previous_request_start() -> None:
    now = 100.0
    delays: list[float] = []

    def monotonic() -> float:
        return now

    async def sleep(delay: float) -> None:
        nonlocal now
        delays.append(delay)
        now += delay

    pacer = ProviderRequestPacer(
        61,
        monotonic=monotonic,
        sleep=sleep,
    )

    async def exercise() -> None:
        nonlocal now
        await pacer.wait()
        now += 12
        await pacer.wait()
        now += 70
        await pacer.wait()

    asyncio.run(exercise())

    assert delays == [49]


@pytest.mark.parametrize("value", [-1, math.inf, math.nan])
def test_provider_pacer_rejects_invalid_intervals(value: float) -> None:
    with pytest.raises(ValueError, match="finite and non-negative"):
        ProviderRequestPacer(value)
