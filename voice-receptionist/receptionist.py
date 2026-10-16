"""Deterministic text simulator for the Peak Plumbing receptionist.

This is the call flow a Retell or Vapi agent follows. It is not a speech model.
The production agent uses config/system-prompt.md plus the tool definitions.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from tools import Calendar, execute, shop_allows

SERVICE_ALIASES = (
    ("water heater", ("water heater", "hot water")),
    ("fixture install", ("faucet", "toilet", "fixture")),
    ("drain cleaning", ("drain", "snake", "clog")),
    ("leak repair", ("leak",)),
)

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+[A-Za-z0-9.'-]+(?:\s+[A-Za-z0-9.'-]+){0,4}\s+"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Way|Boulevard|Blvd)\b"
    r"(?:,?\s*[A-Za-z. ]+)?",
    re.I,
)
NAME_RE = re.compile(r"\b(?:my name is|i'm|i am)\s+([a-z]+(?:\s+[a-z]+){1,2})", re.I)
LEADING_NAME_RE = re.compile(r"^\s*([A-Za-z]+(?:\s+[A-Za-z]+){1,2})\s*,")
PHONE_RE = re.compile(r"(?:\+?1[\s\-.]*)?(?:\(?\d{3}\)?[\s\-.]*)\d{3}[\s\-.]*\d{4}")


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return ""
    return f"({digits[0:3]}) {digits[3:6]}-{digits[6:]}"


def find_city(text: str, knowledge: dict) -> str:
    low = text.lower()
    cities = list(knowledge["service_area"]) + ["Colorado Springs", "Fort Collins", "Boulder", "Pueblo"]
    for city in sorted(cities, key=len, reverse=True):
        if city.lower() in low:
            return city
    return ""


def in_area(city: str, knowledge: dict) -> bool:
    return city.lower() in {name.lower() for name in knowledge["service_area"]}


def speak_slot(day_iso: str, window: str) -> str:
    day = datetime.fromisoformat(day_iso)
    return f"{day.strftime('%A')} {window}"


def extract_window(text: str, now: datetime) -> tuple[str, str]:
    low = text.lower()
    window = "morning" if "morning" in low else "afternoon" if "afternoon" in low else ""
    day = ""
    if "tomorrow" in low:
        day = (now.date() + timedelta(days=1)).isoformat()
    elif "today" in low:
        day = now.date().isoformat()
    else:
        for index, name in enumerate(WEEKDAYS):
            if name in low:
                delta = (index - now.weekday()) % 7
                day = (now.date() + timedelta(days=delta)).isoformat()
                break
    return day, window


def pull_slots(text: str, now: datetime, knowledge: dict) -> dict:
    slots: dict[str, str] = {}
    named = NAME_RE.search(text) or LEADING_NAME_RE.search(text)
    reserved = set(WEEKDAYS) | {"morning", "afternoon", "today", "tomorrow", "yes", "no", "denver"}
    if named and not any(part.lower() in reserved for part in named.group(1).split()):
        slots["caller_name"] = named.group(1).title()
    elif re.fullmatch(r"[A-Za-z]+(?:\s+[A-Za-z]+){1,2}", text.strip()):
        parts = text.strip().split()
        if not any(part.lower() in reserved for part in parts):
            slots["caller_name"] = text.strip().title()
    phone = PHONE_RE.search(text)
    if phone:
        slots["phone"] = normalize_phone(phone.group(0))
    low = text.lower()
    for service, aliases in SERVICE_ALIASES:
        if any(alias in low for alias in aliases):
            slots["service"] = service
            break
    day, window = extract_window(text, now)
    if day:
        slots["day"] = day
    if window:
        slots["window"] = window
    address = ADDRESS_RE.search(text)
    if address:
        slots["address"] = re.sub(r"\s+", " ", address.group(0)).strip(" ,.")
    city = find_city(text, knowledge)
    if city:
        slots["city"] = city
    return slots


def intent_of(text: str) -> str:
    low = text.lower()
    if re.search(r"\b(human|real person|representative|dispatcher|transfer|talk to someone|talk to a person)\b", low):
        return "transfer"
    if re.search(r"\b(flooding|burst|water everywhere|sewage)\b", low) or "emergency" in low:
        return "emergency"
    if re.search(r"\b(how much|price|pricing|cost)\b", low):
        return "pricing"
    if re.search(r"\b(service area|do you serve|come out to|come to|do you come)\b", low):
        return "area"
    if re.search(r"\b(hours|are you open|when do you close|what time)\b", low):
        return "hours"
    if re.search(r"\b(book|schedule|appointment|send someone|need someone)\b", low):
        return "book"
    if re.search(r"\b(bye|goodbye|that is all|that's all|nothing else)\b", low):
        return "goodbye"
    return "unknown"


def is_yes(text: str) -> bool:
    return bool(re.match(r"^\s*(yes|yeah|yep|yup|correct|that works|sounds good|please do|lock it in)\b", text, re.I))


def is_no(text: str) -> bool:
    return bool(re.match(r"^\s*(no|nope|different)\b", text, re.I))


class Receptionist:
    def __init__(self, knowledge: dict, calendar: Calendar, now: datetime):
        self.knowledge = knowledge
        self.calendar = calendar
        self.now = now
        self.slots: dict[str, str] = {}
        self.phase = "listen"
        self.unclear = 0
        self.offers: list[dict] = []
        self.events: list[dict] = []
        self.offered_transfer = False

    def shop_is_open_now(self) -> bool:
        weekday = self.now.strftime("%A").lower()
        hours = self.knowledge["hours"].get(weekday)
        if not hours:
            return False
        current = self.now.strftime("%H:%M")
        return hours[0] <= current < hours[1]

    def greet(self) -> str:
        line = (
            "Thanks for calling Peak Plumbing Denver. "
            "This is the virtual receptionist. How can I help you today?"
        )
        if not self.shop_is_open_now():
            line += " The shop is closed right now. I can take a message or book the next open window."
        self._say(line)
        return line

    def handle(self, text: str) -> list[dict]:
        start = len(self.events)
        self._dispatch(text.strip())
        return self.events[start:]

    def _say(self, text: str) -> None:
        self.events.append({"type": "agent", "text": text})

    def _tool(self, name: str, args: dict) -> dict:
        result = execute(name, args, self.calendar, self.knowledge)
        self.events.append({"type": "tool", "name": name, "arguments": args, "result": result})
        return result

    def _dispatch(self, text: str) -> None:
        if self.offered_transfer and is_yes(text):
            self._transfer("Caller agreed to a transfer after an unclear request.")
            return
        city = find_city(text, self.knowledge)
        if city and not in_area(city, self.knowledge):
            self.phase = "listen"
            self._say(self._outside(city))
            return
        kind = intent_of(text)
        if kind == "transfer":
            self._transfer("Caller asked for a person.")
            return
        if kind == "emergency":
            self._start_emergency(text)
            return
        if self.phase == "message":
            self._collect_message(text)
            return
        if self.phase == "confirm":
            self._confirm(text)
            return
        if self.phase == "choose":
            self._choose(text)
            return
        if kind == "goodbye":
            self.phase = "done"
            self._say("Thanks for calling Peak Plumbing Denver. Goodbye.")
            return
        if self.phase == "collect" and kind in {"hours", "pricing", "area"}:
            self._answer(kind, text)
            self._ask_missing()
            return
        if kind in {"hours", "pricing", "area"}:
            self.unclear = 0
            self._answer(kind, text)
            return
        if kind == "book" or self.phase == "collect":
            self.phase = "collect"
            self.unclear = 0
            self.slots.update({key: value for key, value in pull_slots(text, self.now, self.knowledge).items() if value})
            self._advance_booking()
            return
        self.unclear += 1
        if self.unclear >= 2:
            self.offered_transfer = True
            self._say(
                "I still didn't catch that. I can transfer you to a person at the shop. Want me to do that?"
            )
            return
        self._say("Sorry, I didn't catch that. Are you calling about hours, a price, or booking a visit?")

    def _answer(self, kind: str, text: str) -> None:
        if kind == "hours":
            status = "We're open right now." if self.shop_is_open_now() else "We're closed right now."
            self._say(f"We're open {self.knowledge['hours_spoken']} {status}")
            return
        if kind == "area":
            names = ", ".join(self.knowledge["service_area"])
            self._say(f"We serve {names}.")
            return
        slots = pull_slots(text, self.now, self.knowledge)
        service = slots.get("service")
        if not service:
            self._say(
                "I can give ranges for drain cleaning, water heaters, leak calls, and fixture installs. Which one?"
            )
            return
        blurb = self.knowledge["services"][service]["blurb"]
        self._say(f"{blurb} That's a range, not a firm quote. The plumber confirms the price on site.")

    def _missing(self) -> str:
        for key in ("service", "caller_name", "phone", "day", "window", "address"):
            if not self.slots.get(key):
                return key
        return ""

    def _ask_missing(self) -> None:
        prompts = {
            "service": "What do you need done: a drain, a water heater, a leak, or a fixture?",
            "caller_name": "What's your name?",
            "phone": "What's the best callback number?",
            "day": "What day should I look at?",
            "window": "Do you want morning or afternoon?",
            "address": "What's the street address?",
        }
        missing = self._missing()
        if missing:
            self._say(prompts[missing])

    def _advance_booking(self) -> None:
        if self._missing():
            self._ask_missing()
            return
        city = self.slots.get("city") or find_city(self.slots.get("address", ""), self.knowledge)
        if city and not in_area(city, self.knowledge):
            self.phase = "listen"
            self._say(self._outside(city))
            return
        day, window = self.slots["day"], self.slots["window"]
        if not shop_allows(self.knowledge, day, window):
            self.offers = execute(
                "check_availability",
                {"day": day, "window": window},
                self.calendar,
                self.knowledge,
            )["alternatives"]
            self.phase = "choose"
            self._say(f"We're closed {speak_slot(day, window)}. {self._offer_sentence()}")
            return
        result = self._tool("check_availability", {"day": day, "window": window})
        if not result["open"]:
            self.offers = result["alternatives"]
            self.phase = "choose"
            self._say(f"{speak_slot(day, window)} is already booked. {self._offer_sentence()}")
            return
        self.phase = "confirm"
        self._say(
            f"I can book {self.slots['service']} for {self.slots['caller_name']} on "
            f"{speak_slot(day, window)} at {self.slots['address']}. Should I lock that in?"
        )

    def _offer_sentence(self) -> str:
        if len(self.offers) < 2:
            return "I don't have another window this week."
        first, second = self.offers[:2]
        return (
            f"I can come {speak_slot(first['day'], first['window'])}, "
            f"or {speak_slot(second['day'], second['window'])}. Which works?"
        )

    def _choose(self, text: str) -> None:
        picked = self._match_offer(text)
        if not picked:
            self._say(f"I didn't catch the window. {self._offer_sentence()}")
            return
        self.slots["day"], self.slots["window"] = picked
        self._advance_booking()

    def _match_offer(self, text: str) -> tuple[str, str] | None:
        low = text.lower()
        if "first" in low and self.offers:
            offer = self.offers[0]
            return offer["day"], offer["window"]
        if "second" in low and len(self.offers) > 1:
            offer = self.offers[1]
            return offer["day"], offer["window"]
        day, window = extract_window(text, self.now)
        for offer in self.offers:
            same_window = window and offer["window"] == window
            same_day = day and offer["day"] == day
            if day and window and same_day and same_window:
                return offer["day"], offer["window"]
            if same_window and not day:
                return offer["day"], offer["window"]
        if day and window:
            return day, window
        return None

    def _confirm(self, text: str) -> None:
        kind = intent_of(text)
        if kind in {"hours", "pricing", "area"}:
            self._answer(kind, text)
            self._say(
                f"Should I still lock in {self.slots['service']} for "
                f"{speak_slot(self.slots['day'], self.slots['window'])}?"
            )
            return
        if is_yes(text):
            result = self._tool(
                "book_appointment",
                {
                    "caller_name": self.slots["caller_name"],
                    "phone": self.slots["phone"],
                    "service": self.slots["service"],
                    "day": self.slots["day"],
                    "window": self.slots["window"],
                    "address": self.slots["address"],
                },
            )
            self.phase = "done"
            self._say(
                f"You're booked. Confirmation {result['confirmation']} for "
                f"{speak_slot(self.slots['day'], self.slots['window'])}. "
                f"We'll see you at {self.slots['address']}."
            )
            return
        if is_no(text):
            self.slots.pop("day", None)
            self.slots.pop("window", None)
            self.phase = "collect"
            self._say("No problem. What day and time should I look at instead?")
            return
        self._say("Sorry, should I lock that appointment in? Yes or no.")

    def _start_emergency(self, text: str) -> None:
        self.phase = "message"
        self.slots["message"] = text
        self.slots.update({key: value for key, value in pull_slots(text, self.now, self.knowledge).items() if value})
        if self.slots.get("caller_name") and self.slots.get("phone"):
            self._say(self.knowledge["emergency_line"])
            self._finish_message()
            return
        closed = "" if self.shop_is_open_now() else " The shop is closed. The on-call plumber will call you back about the active leak."
        self._say(
            f"{self.knowledge['emergency_line']}{closed} What's your name and phone number?"
        )

    def _collect_message(self, text: str) -> None:
        self.slots["message"] = f"{self.slots.get('message', '')} {text}".strip()
        self.slots.update({key: value for key, value in pull_slots(text, self.now, self.knowledge).items() if value})
        if not self.slots.get("caller_name") or not self.slots.get("phone"):
            self._say("I still need a name and a callback number.")
            return
        self._finish_message()

    def _finish_message(self) -> None:
        result = self._tool(
            "take_message",
            {
                "caller_name": self.slots["caller_name"],
                "phone": self.slots["phone"],
                "message": self.slots.get("message", ""),
                "address": self.slots.get("address", ""),
            },
        )
        self.phase = "done"
        self._say(
            f"I have that, {self.slots['caller_name']}. "
            f"The on-call plumber will call you back at {self.slots['phone']}. "
            f"Reference {result['reference']}."
        )

    def _transfer(self, reason: str) -> None:
        self._tool("transfer_to_human", {"reason": reason})
        self.phase = "done"
        self._say(
            f"I'm transferring you to a person at the shop now. "
            f"The dispatcher line is {self.knowledge['phone_display']}."
        )

    def _outside(self, city: str) -> str:
        names = ", ".join(self.knowledge["service_area"])
        return f"We don't serve {city}. Peak Plumbing works in {names}."

    def summary(self) -> str:
        tools = [event for event in self.events if event["type"] == "tool"]
        names = [event["name"] for event in tools]
        if "book_appointment" in names:
            outcome = "booked"
            detail = next(event["result"]["confirmation"] for event in tools if event["name"] == "book_appointment")
        elif "transfer_to_human" in names:
            outcome = "transferred"
            detail = self.knowledge["transfer_number"]
        elif "take_message" in names:
            outcome = "message"
            detail = next(event["result"]["reference"] for event in tools if event["name"] == "take_message")
        else:
            outcome = "answered"
            detail = "No follow-up tool was needed."
        caller = self.slots.get("caller_name", "Unknown caller")
        phone = self.slots.get("phone", "No phone")
        return (
            f"Caller: {caller}\n"
            f"Phone: {phone}\n"
            f"Outcome: {outcome}\n"
            f"Detail: {detail}"
        )
