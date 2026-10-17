"""Intent, slots, and the escalation policy the tools enforce."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, timedelta

ORDER_RE = re.compile(r"\bORD-\d{3,}\b", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.IGNORECASE)

REASON_ONLY = {
    "wrong size",
    "too small",
    "too big",
    "too large",
    "too tight",
    "doesnt fit",
    "does not fit",
    "changed my mind",
    "changed mind",
    "unopened",
    "dont want it",
    "do not want it",
    "wore",
    "wore it",
    "worn",
    "washed",
}

FILLER = {
    "a",
    "already",
    "also",
    "an",
    "and",
    "email",
    "for",
    "hello",
    "hey",
    "hi",
    "i",
    "id",
    "is",
    "it",
    "its",
    "just",
    "me",
    "my",
    "no",
    "number",
    "of",
    "on",
    "order",
    "please",
    "thanks",
    "thank",
    "the",
    "this",
    "that",
    "to",
    "yes",
    "you",
}

HIGH_PRIORITY = {"damage_claim", "legal_or_chargeback"}

REASON_LABELS = {
    "outside_window_exception": "Return outside the window",
    "damage_claim": "Damage claim",
    "worn_item": "Worn or washed item",
    "customer_requested_human": "Asked for a person",
    "legal_or_chargeback": "Chargeback or legal",
    "order_not_found": "Order not found",
    "price_match": "Price match",
    "unsupported_request": "Outside desk policy",
    "cancellation": "Cancellation",
    "no_faq_match": "No FAQ match",
    "agent_limit": "Agent stopped",
}

RECOMMENDED = {
    "outside_window_exception": (
        "The published window is closed. Review for a one-time goodwill exception. "
        "Do not refund from this ticket until you decide."
    ),
    "damage_claim": (
        "Ask for photos if you do not have them, then replace or refund. "
        "The agent did not approve a remedy."
    ),
    "worn_item": "The customer says the item was worn or washed. Inspect before any refund.",
    "customer_requested_human": "The customer asked for a person. Take over the conversation.",
    "legal_or_chargeback": (
        "The customer mentioned a chargeback, a lawyer, or a complaint venue. "
        "Respond yourself. Do not debate policy in an automated reply."
    ),
    "order_not_found": (
        "No order matched the id and email the customer gave. Search the back office. "
        "Do not assume the id is real."
    ),
    "price_match": (
        "There is no price-match policy. Decide whether to make an exception and reply "
        "to the customer."
    ),
    "unsupported_request": "The request is outside the tools on this desk. Decide and reply.",
    "cancellation": (
        "If the order has not shipped, cancel it. If it has shipped, tell the customer "
        "and point them at a return."
    ),
    "no_faq_match": (
        "The FAQ had no match. Answer from current policy, and add an FAQ if this will "
        "come up again."
    ),
    "agent_limit": "The agent hit its tool limit before it could finish. Read the transcript and take over.",
}

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


@dataclass(frozen=True)
class Slots:
    order_id: str | None = None
    email: str | None = None
    reason: str = "unspecified"


def norm(text: str) -> str:
    return text.lower().replace("\u2019", "'")


def folded(text: str) -> str:
    return norm(text).replace("'", "")


def format_date(value: str | date | None) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        value = date.fromisoformat(value)
    return f"{MONTHS[value.month - 1]} {value.day}, {value.year}"


def money(amount: float) -> str:
    return f"${amount:,.2f}"


def priority_for(reason_code: str) -> str:
    return "high" if reason_code in HIGH_PRIORITY else "normal"


def label_for(reason_code: str) -> str:
    return REASON_LABELS.get(reason_code, reason_code)


def recommended_for(reason_code: str) -> str:
    return RECOMMENDED.get(reason_code, "Read the transcript and decide.")


def has_legal(text: str) -> bool:
    return bool(
        re.search(
            r"\b(chargeback|lawyer|attorney|lawsuit|sue|bbb|legal action)\b",
            text,
        )
    )


def has_human(text: str) -> bool:
    return bool(
        re.search(
            r"\b(real person|human|representative|manager|live agent)\b",
            text,
        )
        or "talk to a person" in text
        or "talk to someone" in text
        or "someone else" in text
    )


def has_price(text: str) -> bool:
    return (
        "price match" in text
        or "price-match" in text
        or "competitor" in text
        or "found it cheaper" in text
        or "cheaper elsewhere" in text
        or "the pack cheaper" in text
    )


def has_cancel(text: str) -> bool:
    return bool(re.search(r"\bcancel\b", text))


def has_damage(text: str) -> bool:
    return bool(
        re.search(r"\b(damaged|damage|broken|defective|torn)\b", text)
        or "missing item" in text
        or "never arrived" in text
        or "didnt arrive" in text
        or "did not arrive" in text
    )


def has_return_action(text: str) -> bool:
    if re.search(
        r"return policy|refund policy|how do returns|how does a return|can i return|"
        r"do you take returns|whats your return",
        text,
    ):
        return False
    return bool(re.search(r"\b(return|refund|exchange|rma)\b", text))


def has_order_action(raw: str, text: str) -> bool:
    # "How do I track an order?" is a policy question. A live order lookup
    # needs an id, "my order", or a status check.
    if re.search(r"how do i track|where is tracking|tracking number", text):
        return False
    if ORDER_RE.search(raw):
        return True
    return bool(
        re.search(r"\b(where is|track my|order status|status of|my order)\b", text)
        or "has it shipped" in text
        or re.search(r"\bhas\b.+\bshipped\b", text)
    )


def is_greeting(text: str) -> bool:
    stripped = re.sub(r"[^a-z\s]", "", text).strip()
    if stripped in {"hi", "hello", "hey", "good morning", "good afternoon", "help"}:
        return True
    return bool(re.match(r"^(hi|hello|hey)\b", stripped) and len(stripped) < 20)


def is_slot_fill(raw: str) -> bool:
    residual = EMAIL_RE.sub(" ", raw)
    residual = ORDER_RE.sub(" ", residual)
    residual_folded = folded(residual)
    residual_folded = re.sub(r"[^a-z\s]", " ", residual_folded)
    residual_folded = " ".join(residual_folded.split())
    core = " ".join(token for token in residual_folded.split() if token not in FILLER)
    if residual_folded in REASON_ONLY or core in REASON_ONLY:
        return True
    has_slot = bool(ORDER_RE.search(raw) or EMAIL_RE.search(raw))
    if not has_slot:
        return False
    if core == "":
        return True
    tokens = residual_folded.split()
    return bool(tokens) and all(token in FILLER for token in tokens)


def classify_message(raw: str) -> str:
    text = folded(raw)
    if has_legal(text):
        return "legal"
    if has_human(text):
        return "human"
    if has_price(text):
        return "price_match"
    if has_cancel(text):
        return "cancel"
    if has_damage(text):
        return "damage"
    if is_slot_fill(raw):
        return "ambiguous"
    if has_return_action(text):
        return "return"
    if has_order_action(raw, text):
        return "order"
    if is_greeting(text):
        return "greeting"
    return "faq"


def infer_reason(raw: str) -> str:
    text = folded(raw)
    if re.search(r"\b(damaged|damage|broken|defective|torn)\b", text):
        return "damaged"
    if (
        "missing item" in text
        or "never arrived" in text
        or "didnt arrive" in text
        or "did not arrive" in text
    ):
        return "missing"
    if re.search(r"\b(worn|washed)\b", text) or "i wore" in text or "already wore" in text:
        return "worn"
    if any(
        phrase in text
        for phrase in (
            "wrong size",
            "too small",
            "too big",
            "too large",
            "too tight",
            "doesnt fit",
            "does not fit",
            "not fit",
            "size is wrong",
        )
    ):
        return "wrong_size"
    if any(
        phrase in text
        for phrase in (
            "changed my mind",
            "changed mind",
            "unopened",
            "dont want",
            "do not want",
            "dont like",
            "do not like",
            "didnt like",
        )
    ):
        return "changed_mind"
    return "unspecified"


def user_texts(messages: list[dict]) -> list[str]:
    return [message["content"] for message in messages if message.get("role") == "user"]


def request_texts(messages: list[dict]) -> list[str]:
    """The latest request, plus slot-fill follow-ups that belong to it."""
    users = user_texts(messages)
    if not users:
        return []
    picked: list[str] = []
    for text in reversed(users):
        picked.append(text)
        if classify_message(text) != "ambiguous":
            break
    picked.reverse()
    return picked


def extract_slots(messages: list[dict]) -> Slots:
    blob = " ".join(request_texts(messages))
    order_ids = [match.group(0).upper() for match in ORDER_RE.finditer(blob)]
    emails = [match.group(0) for match in EMAIL_RE.finditer(blob)]
    return Slots(
        order_id=order_ids[-1] if order_ids else None,
        email=emails[-1] if emails else None,
        reason=infer_reason(blob),
    )


def with_args(slots: Slots, args: dict) -> Slots:
    order_id = args.get("order_id")
    email = args.get("email")
    reason = args.get("reason")
    if isinstance(order_id, str) and order_id.strip():
        slots = replace(slots, order_id=order_id.strip().upper())
    if isinstance(email, str) and email.strip():
        slots = replace(slots, email=email.strip())
    if isinstance(reason, str) and reason.strip():
        slots = replace(slots, reason=reason.strip())
    return slots


def last_user_text(messages: list[dict]) -> str:
    users = user_texts(messages)
    return users[-1] if users else ""


def item_names(items: list[dict]) -> str:
    names = [str(item["name"]) for item in items]
    if not names:
        return "the item"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def items_with_prices(items: list[dict]) -> str:
    priced = [
        {"name": f"{item['name']} ({money(float(item['price']) * int(item['qty']))})"}
        for item in items
    ]
    return item_names(priced)


def window_end(delivered_on: str, window_days: int) -> date:
    return date.fromisoformat(delivered_on) + timedelta(days=window_days)


def days_since(delivered_on: str, as_of: date) -> int:
    return (as_of - date.fromisoformat(delivered_on)).days
