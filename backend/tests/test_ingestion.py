import pytest
from app.services.ingestion import parse_rss


def test_parse_rss_converts_news_items_to_evidence() -> None:
    xml = """
    <rss><channel>
      <item>
        <title>Services growth update</title>
        <link>https://example.com/news/1</link>
        <description>Revenue context and market demand.</description>
        <pubDate>2026-01-18</pubDate>
      </item>
    </channel></rss>
    """
    evidence = parse_rss(xml, "AAPL")
    assert evidence[0]["id"].startswith("rss-aapl-")
    assert evidence[0]["source_type"] == "news"
    assert evidence[0]["url"] == "https://example.com/news/1"


def test_parse_rss_keeps_ids_stable_when_feed_order_changes() -> None:
    first_item = """
      <item><guid>provider-article-1</guid><title>First article</title>
      <link>https://example.com/news/1</link><pubDate>2026-08-20</pubDate></item>
    """
    new_item = """
      <item><guid>provider-article-2</guid><title>New article</title>
      <link>https://example.com/news/2</link><pubDate>2026-08-21</pubDate></item>
    """

    original = parse_rss(f"<rss><channel>{first_item}</channel></rss>", "AAPL")
    reordered = parse_rss(f"<rss><channel>{new_item}{first_item}</channel></rss>", "AAPL")

    assert original[0]["id"] == reordered[1]["id"]


@pytest.mark.parametrize(
    "entity",
    [
        '<!ENTITY secret "expanded attacker-controlled entity">',
        '<!ENTITY secret SYSTEM "file:///etc/passwd">',
        '<!ENTITY secret SYSTEM "https://example.com/private">',
    ],
)
def test_rss_rejects_entities_before_processing_feed_content(entity: str) -> None:
    xml = f"<!DOCTYPE rss [{entity}]><rss><channel><item><title>&secret;</title></item></channel></rss>"
    with pytest.raises(ValueError, match="Unsafe or invalid RSS feed"):
        parse_rss(xml, "AAPL")


def test_malformed_rss_has_a_stable_import_error() -> None:
    with pytest.raises(ValueError, match="Unsafe or invalid RSS feed"):
        parse_rss("<rss>", "AAPL")
