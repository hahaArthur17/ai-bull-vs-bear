from __future__ import annotations

import pytest

from scripts.verify_supabase_debate_interruption import latency_summary, percentile


def test_hosted_checkpoint_percentile_interpolates_sorted_values() -> None:
    values = [30.0, 10.0, 20.0, 40.0]

    assert percentile(values, 0.50) == 25.0
    assert percentile(values, 0.95) == pytest.approx(38.5)


def test_hosted_checkpoint_latency_summary_is_bounded_metadata_only() -> None:
    assert latency_summary([10.1236, 20.0, 30.0]) == {
        "p50_ms": 20.0,
        "p95_ms": 29.0,
        "mean_ms": 20.041,
        "min_ms": 10.124,
        "max_ms": 30.0,
    }


def test_hosted_checkpoint_percentile_rejects_an_empty_sample() -> None:
    with pytest.raises(ValueError, match="empty sample"):
        percentile([], 0.95)
