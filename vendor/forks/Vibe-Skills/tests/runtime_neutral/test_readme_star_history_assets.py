import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[2]
README_PATHS = (ROOT / "README.md", ROOT / "README.zh.md")
LOCAL_ASSET_PATHS = (
    ROOT / "docs" / "assets" / "star-history-light.svg",
    ROOT / "docs" / "assets" / "star-history-dark.svg",
)
PUBLIC_PAGE_URL = (
    "https://www.star-history.com/"
    "?repos=foryourhealth111-pixel%2FVibe-Skills&type=date&legend=top-left"
)
CHART_URL_PATTERN = re.compile(
    r'https://api\.star-history\.com/chart\?[^"\s<>]+'
)


def test_readmes_use_authorized_live_star_history_embed() -> None:
    for readme_path in README_PATHS:
        readme = readme_path.read_text(encoding="utf-8")
        chart_urls = CHART_URL_PATTERN.findall(readme)

        assert len(chart_urls) == 3
        assert readme.count("https://api.star-history.com") == 3
        assert PUBLIC_PAGE_URL in readme
        assert "./docs/assets/star-history-light.svg" not in readme
        assert "./docs/assets/star-history-dark.svg" not in readme

        queries = []
        for chart_url in chart_urls:
            parsed = urlparse(chart_url)
            assert parsed.scheme == "https"
            assert parsed.netloc == "api.star-history.com"
            assert parsed.path == "/chart"

            query = parse_qs(parsed.query, keep_blank_values=True)
            assert query["repos"] == ["foryourhealth111-pixel/Vibe-Skills"]
            assert query["type"] == ["date"]
            assert query["legend"] == ["top-left"]
            assert len(query.get("sealed_token", [])) == 1
            assert query["sealed_token"][0]
            queries.append(query)

        assert len({query["sealed_token"][0] for query in queries}) == 1
        assert sum(query.get("theme") == ["dark"] for query in queries) == 1
        assert sum("theme" in query for query in queries) == 1


def test_local_star_history_snapshots_are_removed() -> None:
    for asset_path in LOCAL_ASSET_PATHS:
        assert not asset_path.exists()
