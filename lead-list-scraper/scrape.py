"""Scrape the bundled Denver plumber directory and write a cleaned CSV.

Default mode reads the HTML fixtures from disk. Pass --url to crawl a local
server that is hosting those same files. This tool does not call Google Maps.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from fixtures_gen import build_listings, write_fixtures
from leads import parse_html, prepare, write_csv

ROOT = Path(__file__).resolve().parent
FIXTURE_DIR = ROOT / "fixtures"
OUTPUT_DIR = ROOT / "output"


def crawl(start_url: str) -> list[tuple[str, str]]:
    origin = urllib.parse.urlparse(start_url)
    seen: set[str] = set()
    queue = [start_url]
    pages: list[tuple[str, str]] = []
    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        with urllib.request.urlopen(url, timeout=10) as response:
            html = response.read().decode("utf-8")
        pages.append((url, html))
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a.page"):
            href = link.get("href")
            if not href:
                continue
            nxt = urllib.parse.urljoin(url, str(href))
            parsed = urllib.parse.urlparse(nxt)
            if parsed.netloc == origin.netloc:
                queue.append(nxt)
    return pages


def load_fixture_pages(directory: Path) -> list[tuple[str, str]]:
    pages = []
    for path in sorted(directory.glob("*.html")):
        source = f"Front Range Business Index/{path.name}"
        pages.append((source, path.read_text(encoding="utf-8")))
    return pages


def render_summary_html(summary: dict, rows: list[dict]) -> str:
    preview = rows[:8]
    body = "".join(
        "<tr>"
        + "".join(f"<td>{_esc(row[key])}</td>" for key in ("name", "phone", "website", "rating", "email", "address"))
        + "</tr>"
        for row in preview
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Denver plumbers — cleaned lead list</title>
  <style>
    body {{ margin: 0; background: #eef3ef; color: #17211b; font-family: "Avenir Next", "Segoe UI", sans-serif; }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 36px 24px 64px; }}
    h1 {{ font-family: Georgia, serif; font-weight: 500; font-size: 40px; margin: 0; }}
    .note {{ max-width: 640px; color: #3e5146; }}
    .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 24px 0; }}
    .stat {{ background: white; border-radius: 16px; padding: 16px; }}
    .stat b {{ display: block; font-size: 32px; font-family: Georgia, serif; font-weight: 500; }}
    .stat span {{ color: #5c6d63; font-size: 13px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 16px; overflow: hidden; font-size: 13px; }}
    th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #e4eee7; vertical-align: top; }}
    th {{ font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: #5c6d63; }}
    @media (max-width: 800px) {{ .stats {{ grid-template-columns: 1fr 1fr; }} }}
  </style>
</head>
<body>
  <main>
    <p>Gig 3 sample · collected {summary['collected_date']}</p>
    <h1>Denver plumbers</h1>
    <p class="note">{_esc(summary['source'])}. Chains removed, phones normalized, duplicates merged.</p>
    <div class="stats">
      <div class="stat"><b>{summary['rows']}</b><span>cleaned rows</span></div>
      <div class="stat"><b>{summary['duplicates_removed']}</b><span>duplicates merged</span></div>
      <div class="stat"><b>{summary['pct_with_email']}%</b><span>with a public email</span></div>
      <div class="stat"><b>{summary['pct_with_website']}%</b><span>with a website</span></div>
    </div>
    <table>
      <thead><tr><th>Name</th><th>Phone</th><th>Website</th><th>Rating</th><th>Email</th><th>Address</th></tr></thead>
      <tbody>{body}</tbody>
    </table>
  </main>
</body>
</html>
"""


def _esc(value: str) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def run(pages: list[tuple[str, str]], collected_date: str, out_dir: Path) -> tuple[list[dict], dict]:
    listings = []
    for source, html in pages:
        listings.extend(parse_html(html, source))
    rows, summary = prepare(listings, collected_date)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "denver-plumbers.csv", rows)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out_dir / "summary.html").write_text(render_summary_html(summary, rows), encoding="utf-8")
    return rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a cleaned Denver plumber lead list from fixtures.")
    parser.add_argument("--url", help="Crawl a local fixture server instead of the files on disk.")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--out", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--fixtures", type=Path, default=FIXTURE_DIR)
    args = parser.parse_args()
    write_fixtures(args.fixtures, build_listings())
    pages = crawl(args.url) if args.url else load_fixture_pages(args.fixtures)
    if args.url:
        pages = [(url, html) for url, html in pages]
    rows, summary = run(pages, args.date, args.out)
    print(
        f"{summary['rows']} rows from {summary['raw_rows']} raw listings "
        f"({summary['duplicates_removed']} dupes, {summary['chains_excluded']} chains)."
    )
    print(f"Wrote {args.out / 'denver-plumbers.csv'}")


if __name__ == "__main__":
    main()
