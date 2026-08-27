import pytest

from app.services.stock_catalog import CatalogSnapshotError, build_catalog_snapshot


SOURCE_SHA256 = "a" * 64


def payload(*rows: list[object]) -> dict[str, object]:
    return {
        "fields": ["cik", "name", "ticker", "exchange"],
        "data": list(rows),
    }


def test_build_catalog_snapshot_filters_and_normalizes_deterministically() -> None:
    snapshot = build_catalog_snapshot(
        payload(
            [2, "  Apple   Inc. ", "aapl", "Nasdaq"],
            [3, "OTC Issuer", "OTCI", "OTC"],
            [1, "Cboe Global Markets", "CBOE", "CBOE"],
            [4, "No Exchange", "NONE", None],
        ),
        retrieved_on="2026-08-27",
        source_sha256=SOURCE_SHA256,
    )

    assert snapshot["source"] == {
        "url": "https://www.sec.gov/files/company_tickers_exchange.json",
        "retrieved_on": "2026-08-27",
        "sha256": SOURCE_SHA256,
        "raw_row_count": 4,
    }
    assert snapshot["transformation"] == {
        "version": "sec-exchange-v1",
        "allowed_source_exchanges": ["CBOE", "NYSE", "Nasdaq"],
        "max_rows": 10_000,
        "excluded_row_count": 2,
    }
    assert snapshot["stocks"] == [
        {
            "sec_cik": 2,
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "exchange": "NASDAQ",
        },
        {
            "sec_cik": 1,
            "ticker": "CBOE",
            "company_name": "Cboe Global Markets",
            "exchange": "CBOE",
        },
    ]


def test_build_catalog_snapshot_rejects_upstream_schema_drift() -> None:
    with pytest.raises(CatalogSnapshotError, match="expected schema"):
        build_catalog_snapshot(
            {"fields": ["ticker", "name"], "data": []},
            retrieved_on="2026-08-27",
            source_sha256=SOURCE_SHA256,
        )


def test_build_catalog_snapshot_rejects_duplicate_tickers() -> None:
    with pytest.raises(CatalogSnapshotError, match="Duplicate normalized ticker AAPL"):
        build_catalog_snapshot(
            payload(
                [1, "Apple", "AAPL", "Nasdaq"],
                [2, "Another Apple", "aapl", "NYSE"],
            ),
            retrieved_on="2026-08-27",
            source_sha256=SOURCE_SHA256,
        )


def test_build_catalog_snapshot_enforces_row_safety_limit() -> None:
    with pytest.raises(CatalogSnapshotError, match="row safety limit"):
        build_catalog_snapshot(
            payload(
                [1, "Apple", "AAPL", "Nasdaq"],
                [2, "Microsoft", "MSFT", "Nasdaq"],
            ),
            retrieved_on="2026-08-27",
            source_sha256=SOURCE_SHA256,
            max_rows=1,
        )


@pytest.mark.parametrize(
    ("retrieved_on", "source_sha256"),
    [("27-08-2026", SOURCE_SHA256), ("2026-08-27", "not-a-digest")],
)
def test_build_catalog_snapshot_validates_provenance(
    retrieved_on: str,
    source_sha256: str,
) -> None:
    with pytest.raises(CatalogSnapshotError):
        build_catalog_snapshot(
            payload([1, "Apple", "AAPL", "Nasdaq"]),
            retrieved_on=retrieved_on,
            source_sha256=source_sha256,
        )
