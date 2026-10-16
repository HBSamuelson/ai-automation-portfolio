import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fixtures_gen import build_listings, write_fixtures
from leads import dedupe, normalize_phone, parse_html, prepare
from scrape import crawl, run

TINY = """
<article class="listing" data-chain="false">
  <h2>Mile High Peak Plumbing</h2>
  <p class="phone">303.555.0100</p>
  <a class="website" href="WWW.MileHigh.Example">site</a>
  <p class="address">10   Perry Street</p>
  <p class="city">Denver, CO</p>
  <p class="rating">4.8 stars</p>
</article>
<article class="listing" data-chain="false">
  <h2>Mile High Peak Plumbing LLC</h2>
  <p class="phone">+1 303-555-0100</p>
  <p class="address">10 Perry Street</p>
  <p class="city">Denver, CO</p>
  <p class="rating" data-rating="4.9">4.9 stars</p>
  <a class="email" href="mailto:Office@MileHigh.Example">Office@MileHigh.Example</a>
</article>
<article class="listing" data-chain="true">
  <h2>FlowRight National Plumbing</h2>
  <p class="phone">(303) 555-0199</p>
  <p class="address">1 Broadway</p>
  <p class="city">Denver, CO</p>
</article>
<article class="listing">
  <h2>Ask For Mike Plumbing</h2>
  <p class="phone">ask for Mike</p>
  <p class="address">2 Maple Avenue</p>
  <p class="city">Denver, CO</p>
</article>
"""


def test_phone_and_dedupe_merge_email():
    assert normalize_phone("1-303-555-0100") == "(303) 555-0100"
    assert normalize_phone("ask for Mike") == ""
    rows, summary = prepare(parse_html(TINY, "fixture"), "2026-10-15")
    assert summary["chains_excluded"] == 1
    assert summary["invalid_phone_dropped"] == 1
    assert summary["duplicates_removed"] == 1
    assert len(rows) == 1
    assert rows[0]["phone"] == "(303) 555-0100"
    assert rows[0]["email"] == "office@milehigh.example"
    assert rows[0]["website"] == "https://www.milehigh.example"
    assert rows[0]["rating"] == "4.9"
    assert "FlowRight" not in rows[0]["name"]


def test_dedupe_is_stable_by_phone():
    rows = dedupe(
        [
            {"name": "A", "phone": "(303) 555-0101", "website": "", "email": "", "rating": "", "address": "1"},
            {"name": "A LLC", "phone": "(303) 555-0101", "website": "https://a.example", "email": "a@a.example", "rating": "4.0", "address": "1"},
        ]
    )
    assert len(rows) == 1
    assert rows[0]["email"] == "a@a.example"
    assert rows[0]["website"] == "https://a.example"


def test_full_fixture_counts(tmp_path: Path):
    listings = build_listings()
    assert len(listings) == 340
    write_fixtures(tmp_path / "fixtures", listings)
    pages = [
        (path.name, path.read_text(encoding="utf-8"))
        for path in sorted((tmp_path / "fixtures").glob("*.html"))
    ]
    rows, summary = run(pages, "2026-10-15", tmp_path / "out")
    assert summary["raw_rows"] == 340
    assert summary["rows"] == 300
    assert summary["chains_excluded"] == 12
    assert summary["invalid_phone_dropped"] == 4
    assert summary["duplicates_removed"] == 24
    phones = [row["phone"] for row in rows]
    assert len(phones) == len(set(phones))
    assert all(not row["name"].lower().startswith("flowright") for row in rows)
    assert (tmp_path / "out" / "denver-plumbers.csv").exists()
    filled = next(row for row in rows if row["email"].startswith("office@"))
    assert filled["email"].endswith(".example")


def test_http_crawl_of_fixtures(tmp_path: Path):
    write_fixtures(tmp_path, build_listings())

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(tmp_path), **kwargs)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        pages = crawl(f"http://127.0.0.1:{port}/index.html")
    finally:
        server.shutdown()
    assert len(pages) == 3
    rows, summary = prepare(
        [listing for url, html in pages for listing in parse_html(html, url)],
        "2026-10-15",
    )
    assert summary["rows"] == 300
    assert len(rows) == 300
