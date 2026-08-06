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
    assert evidence[0]["id"] == "rss-aapl-001"
    assert evidence[0]["source_type"] == "news"
    assert evidence[0]["url"] == "https://example.com/news/1"
