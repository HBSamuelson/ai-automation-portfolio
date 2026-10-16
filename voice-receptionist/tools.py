"""Tool schemas shared by the Vapi/Retell configs and the text simulator."""

from __future__ import annotations

from datetime import date, timedelta

TOOL_SCHEMAS = [
    {
        "name": "check_availability",
        "description": "Check whether a morning or afternoon window is open before offering it.",
        "parameters": {
            "type": "object",
            "properties": {
                "day": {"type": "string", "description": "ISO date, YYYY-MM-DD."},
                "window": {"type": "string", "enum": ["morning", "afternoon"]},
            },
            "required": ["day", "window"],
        },
    },
    {
        "name": "book_appointment",
        "description": "Book a confirmed 90-minute visit. Call only after the caller says yes.",
        "parameters": {
            "type": "object",
            "properties": {
                "caller_name": {"type": "string"},
                "phone": {"type": "string"},
                "service": {
                    "type": "string",
                    "enum": ["drain cleaning", "water heater", "leak repair", "fixture install"],
                },
                "day": {"type": "string"},
                "window": {"type": "string", "enum": ["morning", "afternoon"]},
                "address": {"type": "string"},
            },
            "required": ["caller_name", "phone", "service", "day", "window", "address"],
        },
    },
    {
        "name": "take_message",
        "description": "Save a callback message when the shop is closed or the caller will not book.",
        "parameters": {
            "type": "object",
            "properties": {
                "caller_name": {"type": "string"},
                "phone": {"type": "string"},
                "message": {"type": "string"},
                "address": {"type": "string"},
            },
            "required": ["caller_name", "phone", "message"],
        },
    },
    {
        "name": "transfer_to_human",
        "description": "Transfer the caller to the Peak Plumbing dispatcher.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
            },
            "required": ["reason"],
        },
    },
]


def shop_allows(knowledge: dict, day_iso: str, window: str) -> bool:
    weekday = date.fromisoformat(day_iso).strftime("%A").lower()
    hours = knowledge["hours"].get(weekday)
    if not hours:
        return False
    if weekday == "saturday" and window == "afternoon":
        return False
    return window in {"morning", "afternoon"}


def alternatives(calendar, knowledge: dict, day_iso: str, window: str, limit: int = 2) -> list[dict]:
    start = date.fromisoformat(day_iso)
    ordered: list[tuple[str, str]] = []
    for offset in range(0, 14):
        current = (start + timedelta(days=offset)).isoformat()
        for candidate in ("morning", "afternoon"):
            ordered.append((current, candidate))
    index = ordered.index((day_iso, window))
    found = []
    for day, candidate in ordered[index + 1 :]:
        if shop_allows(knowledge, day, candidate) and calendar.is_open(day, candidate):
            found.append({"day": day, "window": candidate})
        if len(found) == limit:
            break
    return found


class Calendar:
    def __init__(self, busy: set[tuple[str, str]] | None = None):
        self.busy = set(busy or set())
        self.bookings: list[dict] = []
        self.messages: list[dict] = []
        self.transfers: list[dict] = []

    def is_open(self, day: str, window: str) -> bool:
        return (day, window) not in self.busy

    def book(self, args: dict) -> str:
        self.busy.add((args["day"], args["window"]))
        confirmation = f"PP-{1000 + len(self.bookings) + 1}"
        self.bookings.append({**args, "confirmation": confirmation})
        return confirmation


def execute(name: str, args: dict, calendar: Calendar, knowledge: dict) -> dict:
    if name == "check_availability":
        allowed = shop_allows(knowledge, args["day"], args["window"])
        open_slot = allowed and calendar.is_open(args["day"], args["window"])
        return {
            "open": open_slot,
            "alternatives": alternatives(calendar, knowledge, args["day"], args["window"]),
        }
    if name == "book_appointment":
        if not calendar.is_open(args["day"], args["window"]) or not shop_allows(
            knowledge, args["day"], args["window"]
        ):
            return {"ok": False, "error": "That window is not open."}
        confirmation = calendar.book(args)
        return {"ok": True, "confirmation": confirmation}
    if name == "take_message":
        calendar.messages.append(args)
        return {"ok": True, "reference": f"MSG-{100 + len(calendar.messages)}"}
    if name == "transfer_to_human":
        calendar.transfers.append(args)
        return {"ok": True, "number": knowledge["transfer_number"]}
    raise KeyError(name)
