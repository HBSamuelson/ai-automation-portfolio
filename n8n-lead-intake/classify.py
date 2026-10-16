"""Offline lead classification for the Northline Studio intake demo.

The importable n8n workflow asks OpenAI to apply the same rules. This module
is the stand-in the sample run uses when no API key is set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HOT_PHRASES = (
    "urgent",
    "asap",
    "as soon as possible",
    "this week",
    "ready to start",
    "ready to buy",
    "budget approved",
    "budget is approved",
    "decision maker",
    "call me today",
    "immediately",
    "signed off",
)

WARM_PHRASES = (
    "pricing",
    "price",
    "quote",
    "interested",
    "next month",
    "evaluating",
    "demo",
    "timeline",
    "comparing",
)

COLD_PHRASES = (
    "just curious",
    "just looking",
    "student",
    "no budget",
    "someday",
    "not sure",
    "maybe later",
    "researching for school",
)

NEXT_STEP = {
    "hot": "call today",
    "warm": "send pricing",
    "cold": "nurture only",
}


@dataclass(frozen=True)
class Lead:
    name: str
    email: str
    company: str
    phone: str
    source: str
    message: str


@dataclass(frozen=True)
class Classification:
    temperature: str
    summary: str
    reason: str

    def summary_lines(self) -> list[str]:
        return self.summary.split("\n")


def normalize_lead(raw: dict) -> Lead:
    def text(key: str) -> str:
        return re.sub(r"\s+", " ", str(raw.get(key) or "")).strip()

    name = text("name").title()
    email = text("email").lower()
    return Lead(
        name=name,
        email=email,
        company=text("company"),
        phone=text("phone"),
        source=text("source") or "website-form",
        message=text("message"),
    )


def valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def _blob(lead: Lead) -> str:
    return f"{lead.message} {lead.company} {lead.source}".lower()


def _hits(blob: str, phrases: tuple[str, ...]) -> list[str]:
    return [phrase for phrase in phrases if phrase in blob]


def classify(lead: Lead) -> Classification:
    blob = _blob(lead)
    hot_hits = _hits(blob, HOT_PHRASES)
    warm_hits = _hits(blob, WARM_PHRASES)
    cold_hits = _hits(blob, COLD_PHRASES)

    if any(phrase in blob for phrase in ("no budget", "just curious", "researching for school")):
        temperature = "cold"
        reason = "The note shows curiosity or no budget, so it is not a live opportunity."
    elif hot_hits:
        temperature = "hot"
        reason = f"The note signals near-term intent ({hot_hits[0]})."
    elif warm_hits:
        temperature = "warm"
        reason = f"The note asks for information ({warm_hits[0]}) without a start-now signal."
    elif cold_hits:
        temperature = "cold"
        reason = f"The note is low intent ({cold_hits[0]})."
    elif lead.company:
        temperature = "warm"
        reason = "A company is named, but the note does not say how soon they want to start."
    else:
        temperature = "cold"
        reason = "There is no company and no clear buying signal."

    who = lead.name or "Unknown sender"
    if lead.company:
        who = f"{who} at {lead.company}"
    want = lead.message.rstrip(".") or "did not describe a project"
    if len(want) > 110:
        want = want[:107].rstrip() + "..."
    line_1 = f"{who} wrote: {want}."
    line_2 = (
        f"{temperature.capitalize()} lead because {reason} "
        f"Next step: {NEXT_STEP[temperature]}."
    )
    return Classification(temperature=temperature, summary=f"{line_1}\n{line_2}", reason=reason)


def email_copy(lead: Lead, result: Classification) -> tuple[str, str]:
    first = lead.name.split(" ")[0] if lead.name else "there"
    subject = {
        "hot": "We got your note and will call today",
        "warm": "Pricing next steps from Northline Studio",
        "cold": "Thanks for contacting Northline Studio",
    }[result.temperature]
    body = {
        "hot": (
            f"Hi {first},\n\n"
            "Thanks for writing in. A specialist will call you today about the workflow you described.\n\n"
            "Northline Studio"
        ),
        "warm": (
            f"Hi {first},\n\n"
            "Thanks for your interest. Reply with two times that work for a 15-minute call, "
            "and we will send a short pricing outline before we meet.\n\n"
            "Northline Studio"
        ),
        "cold": (
            f"Hi {first},\n\n"
            "Thanks for getting in touch. If a workflow project comes up later, reply to this note "
            "and we will pick it up from there.\n\n"
            "Northline Studio"
        ),
    }[result.temperature]
    return subject, body


def slack_text(lead: Lead, result: Classification) -> str:
    return "\n".join(
        [
            f"*Hot lead:* {lead.name or 'Unknown'} · {lead.company or 'No company'}",
            lead.email,
            lead.phone or "No phone",
            "",
            result.summary,
            "",
            f"Source: {lead.source}",
        ]
    )
