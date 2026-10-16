# Denver plumber lead list

A cleaned lead list for a fictional niche: plumbers in Denver. The source is the **Front Range Business Index**, a local HTML fixture in this folder. It is not Google Maps, not a live directory, and not someone else's site.

Every phone number uses the 555 exchange. Every website and email is on `.example`. Chain listings named FlowRight are removed. Duplicate phones are merged, and the row that has the email or the higher rating fills the gaps.

## Run

```bash
python3 -m pip install -r requirements.txt
python3 scrape.py --date 2026-10-15
python3 -m pytest -q tests
```

Outputs:

- `output/denver-plumbers.csv` — 300 rows
- `output/summary.json` — counts and the percent with email or a website
- `output/summary.html` — a one-page summary
- `fixtures/` — the HTML the scraper reads

`scrape.py` rewrites the fixtures, then parses them from disk. To prove the HTTP path, the tests serve those files on localhost and crawl `index.html` plus the two linked pages.

Columns: name, phone, website, address, city, rating, email, niche, source, collected_date.

## What this is not

A delivery for a real buyer would use a source whose terms allow the collection, and it would record that source and the collection date the same way this CSV does. This demo does not ship a Google Maps scraper.
