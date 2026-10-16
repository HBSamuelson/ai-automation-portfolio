"""Parse, clean, and dedupe plumber listings from the fixture directory."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

CHAIN_MARKERS = ("flowright", "pipenation")
CSV_FIELDS = [
    "name",
    "phone",
    "website",
    "address",
    "city",
    "rating",
    "email",
    "niche",
    "source",
    "collected_date",
]


@dataclass
class RawListing:
    name: str
    phone: str
    website: str
    address: str
    city: str
    rating: str
    email: str
    chain: bool
    source: str


def parse_html(html: str, source: str) -> list[RawListing]:
    soup = BeautifulSoup(html, "html.parser")
    listings: list[RawListing] = []
    for card in soup.select("article.listing"):
        def text(selector: str) -> str:
            node = card.select_one(selector)
            return node.get_text(" ", strip=True) if node else ""

        website = card.select_one("a.website")
        email = card.select_one("a.email")
        email_value = ""
        if email and email.get("href"):
            email_value = str(email.get("href"))
        elif email:
            email_value = email.get_text(" ", strip=True)
        name = text("h2")
        chain = card.get("data-chain") == "true" or any(marker in name.lower() for marker in CHAIN_MARKERS)
        listings.append(
            RawListing(
                name=name,
                phone=text(".phone"),
                website=str(website.get("href") or "") if website else "",
                address=text(".address"),
                city=text(".city") or "Denver, CO",
                rating=str(card.select_one(".rating").get("data-rating") or "")
                if card.select_one(".rating") and card.select_one(".rating").get("data-rating")
                else text(".rating"),
                email=email_value,
                chain=chain,
                source=source,
            )
        )
    return listings


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return ""
    return f"({digits[0:3]}) {digits[3:6]}-{digits[6:]}"


def normalize_website(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if value.startswith("www."):
        value = "https://" + value
    if not value.startswith("http://") and not value.startswith("https://"):
        value = "https://" + value
    return value.lower().rstrip("/")


def normalize_email(raw: str) -> str:
    value = (raw or "").strip().lower()
    value = value.removeprefix("mailto:")
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        return value
    return ""


def normalize_rating(raw: str) -> str:
    match = re.search(r"\d+(?:\.\d+)?", raw or "")
    if not match:
        return ""
    number = float(match.group(0))
    if number < 0 or number > 5:
        return ""
    return f"{number:.1f}"


def clean_listing(raw: RawListing, collected_date: str) -> dict | None:
    if raw.chain:
        return None
    phone = normalize_phone(raw.phone)
    if not phone:
        return None
    name = re.sub(r"\s+", " ", raw.name).strip()
    name = re.sub(r"\s+LLC$", "", name, flags=re.I).strip()
    return {
        "name": name,
        "phone": phone,
        "website": normalize_website(raw.website),
        "address": re.sub(r"\s+", " ", raw.address).strip(),
        "city": raw.city.strip() or "Denver, CO",
        "rating": normalize_rating(raw.rating),
        "email": normalize_email(raw.email),
        "niche": "Plumber",
        "source": raw.source,
        "collected_date": collected_date,
    }


def dedupe(rows: list[dict]) -> list[dict]:
    kept: dict[str, dict] = {}
    for row in rows:
        current = kept.get(row["phone"])
        if current is None:
            kept[row["phone"]] = dict(row)
            continue
        for key in ("website", "email", "address"):
            if not current.get(key) and row.get(key):
                current[key] = row[key]
        if row.get("rating") and (
            not current.get("rating") or float(row["rating"]) > float(current["rating"])
        ):
            current["rating"] = row["rating"]
        if not current.get("name") and row.get("name"):
            current["name"] = row["name"]
    return sorted(kept.values(), key=lambda row: row["name"].lower())


def prepare(listings: list[RawListing], collected_date: str) -> tuple[list[dict], dict]:
    chains = sum(1 for listing in listings if listing.chain)
    cleaned = []
    invalid = 0
    for listing in listings:
        if listing.chain:
            continue
        row = clean_listing(listing, collected_date)
        if row is None:
            invalid += 1
            continue
        cleaned.append(row)
    deduped = dedupe(cleaned)
    duplicates = len(cleaned) - len(deduped)
    with_email = sum(1 for row in deduped if row["email"])
    with_website = sum(1 for row in deduped if row["website"])
    total = len(deduped) or 1
    summary = {
        "rows": len(deduped),
        "raw_rows": len(listings),
        "chains_excluded": chains,
        "invalid_phone_dropped": invalid,
        "duplicates_removed": duplicates,
        "pct_with_email": round(100 * with_email / total, 1),
        "pct_with_website": round(100 * with_website / total, 1),
        "niche": "Plumbers",
        "city": "Denver, CO",
        "source": "Front Range Business Index (local fixture, not Google Maps)",
        "collected_date": collected_date,
    }
    return deduped, summary


def write_csv(path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
