"""Write the fictional Front Range Business Index HTML pages.

Listings use 555 phone numbers and .example websites. Nothing here is scraped
from Google Maps or from a live directory.
"""

from __future__ import annotations

import random
import re
from pathlib import Path

ADJECTIVES = [
    "Mile High", "Front Range", "Colfax", "Platte", "Capitol", "Cherry Creek",
    "Sloan", "Highland", "Wash Park", "RiNo", "Baker", "Five Points", "Congress Park",
    "City Park", "Speer", "Berkeley", "Sun Valley", "Athmar", "Barnum", "Harvey Park",
    "Virginia Village", "Hale", "Montclair", "Skyland", "Whittier",
]
PLACES = [
    "Peak", "Union", "Larimer", "Broadway", "Federal", "Colorado", "York", "Downing",
    "Alameda", "Evans", "Mississippi", "Cedar", "Maple", "Aspen", "Spruce", "Ridge",
]
KINDS = ["Plumbing", "Plumbing Co.", "Drain and Pipe", "Pipeworks"]
STREETS = [
    "Perry Street", "Galapago Street", "Irving Street", "Ogden Street", "Pearl Street",
    "Clarkson Street", "Emerson Street", "Franklin Street", "Gaylord Street", "High Street",
    "Jason Street", "Kalamath Street", "Lipan Street", "Mariposa Street", "Navajo Street",
]
NEIGHBORHOODS = [
    "Capitol Hill", "Highlands", "RiNo", "Wash Park", "Baker", "Congress Park",
    "City Park", "Berkeley", "Sloan Lake", "Five Points",
]
ZIPS = ["80203", "80204", "80205", "80206", "80209", "80210", "80211", "80218", "80220", "80223"]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _phone(rng: random.Random, index: int, messy: bool) -> str:
    area = "303" if index % 2 == 0 else "720"
    number = f"{area}555{1000 + index:04d}"
    if not messy:
        return f"({number[0:3]}) {number[3:6]}-{number[6:]}"
    style = index % 5
    if style == 0:
        return f"{number[0:3]}.{number[3:6]}.{number[6:]}"
    if style == 1:
        return number
    if style == 2:
        return f"+1 {number[0:3]}-{number[3:6]}-{number[6:]}"
    if style == 3:
        return f"1-{number[0:3]}-{number[3:6]}-{number[6:]}"
    return f"({number[0:3]}) {number[3:6]}-{number[6:]}"


def build_listings(seed: int = 20261015) -> list[dict]:
    rng = random.Random(seed)
    combos = [(adj, place, kind) for adj in ADJECTIVES for place in PLACES for kind in KINDS]
    rng.shuffle(combos)
    listings = []
    for index, (adj, place, kind) in enumerate(combos[:300]):
        name = f"{adj} {place} {kind}"
        slug = _slug(name)
        number = rng.randint(100, 1899)
        street = rng.choice(STREETS)
        neighborhood = rng.choice(NEIGHBORHOODS)
        zip_code = rng.choice(ZIPS)
        rating = "" if rng.random() < 0.05 else f"{rng.uniform(3.2, 5.0):.1f}"
        website = "" if rng.random() < 0.18 else f"https://{slug}.example"
        email = "" if rng.random() < 0.54 else f"info@{slug}.example"
        listings.append(
            {
                "name": name,
                "phone": _phone(rng, index, messy=index % 4 == 0),
                "website": website,
                "address": f"{number} {street}, {neighborhood}, Denver, CO {zip_code}",
                "city": "Denver, CO",
                "rating": rating,
                "email": email,
                "chain": False,
            }
        )

    for offset, original in enumerate(listings[:24]):
        clone = dict(original)
        clone["name"] = original["name"] + " LLC"
        clone["website"] = "" if offset % 2 == 0 else original["website"]
        if not original["email"]:
            clone["email"] = f"office@{_slug(original['name'])}.example"
        else:
            clone["email"] = original["email"].upper()
        listings.append(clone)

    for index in range(12):
        listings.append(
            {
                "name": "FlowRight National Plumbing",
                "phone": _phone(rng, 400 + index, messy=False),
                "website": "https://flowright.example",
                "address": f"{200 + index} Broadway, Downtown, Denver, CO 80202",
                "city": "Denver, CO",
                "rating": "4.2",
                "email": "franchise@flowright.example",
                "chain": True,
            }
        )

    for index in range(4):
        listings.append(
            {
                "name": f"Ask For Mike Plumbing {index + 1}",
                "phone": "ask for Mike",
                "website": "",
                "address": f"{10 + index} Maple Avenue, Baker, Denver, CO 80204",
                "city": "Denver, CO",
                "rating": "5.0",
                "email": "",
                "chain": False,
            }
        )
    return listings


def render_page(title: str, listings: list[dict], next_href: str | None) -> str:
    cards = []
    for listing in listings:
        website = (
            f'<a class="website" href="{listing["website"]}">{listing["website"]}</a>'
            if listing["website"]
            else ""
        )
        email = (
            f'<a class="email" href="mailto:{listing["email"]}">{listing["email"]}</a>'
            if listing["email"]
            else ""
        )
        rating = (
            f'<p class="rating" data-rating="{listing["rating"]}">{listing["rating"]} stars</p>'
            if listing["rating"]
            else "<p class=\"rating\">No rating</p>"
        )
        cards.append(
            f"""<article class="listing" data-chain="{'true' if listing['chain'] else 'false'}">
  <h2>{listing['name']}</h2>
  <p class="phone">{listing['phone']}</p>
  {website}
  <p class="address">{listing['address']}</p>
  <p class="city">{listing['city']}</p>
  {rating}
  {email}
</article>"""
        )
    pager = f'<nav><a class="page" href="{next_href}">Next page</a></nav>' if next_href else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{title}</title></head>
<body>
  <header>
    <p>Front Range Business Index — fictional sample directory for a portfolio demo. Not Google Maps. Not a live site.</p>
    <h1>{title}</h1>
  </header>
  <main>
    {''.join(cards)}
  </main>
  {pager}
</body>
</html>
"""


def write_fixtures(directory: Path, listings: list[dict] | None = None) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    listings = listings if listings is not None else build_listings()
    pages = [listings[0:120], listings[120:240], listings[240:]]
    names = ["index.html", "page-2.html", "page-3.html"]
    next_pages = ["page-2.html", "page-3.html", None]
    written = []
    for name, chunk, nxt in zip(names, pages, next_pages):
        path = directory / name
        title = "Denver plumbers" if name == "index.html" else f"Denver plumbers ({name})"
        path.write_text(render_page(title, chunk, nxt), encoding="utf-8")
        written.append(path)
    return written
