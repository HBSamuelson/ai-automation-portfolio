"""Customer-facing copy for the offline mock planner.

Live mode writes its own reply. Ticket text is still assembled in the tools,
from verified order data, so a person is not reading a model's guess.
"""

from __future__ import annotations

from support_agent.policy import (
    Slots,
    format_date,
    item_names,
    items_with_prices,
    money,
    window_end,
)

GREETING = (
    "Hi, this is Northline support. I can check an order, start a standard return, "
    "or answer questions on shipping, sizing, and warranty. What do you need?"
)


def ask_for_identity(goal: str, slots: Slots) -> str:
    if goal == "cancel":
        action = "I can hand a cancellation to a person"
    elif goal == "damage":
        action = "I can get a damage claim to a person"
    elif goal == "return":
        action = "I can check that return"
    else:
        action = "I can look that up"
    needs_order = slots.order_id is None
    needs_email = slots.email is None
    if needs_order and needs_email:
        return (
            f"{action}, and I need two things: the order number (it looks like ORD-1042) "
            "and the email on the order."
        )
    if needs_order:
        return f"{action}. I still need the order number. It looks like ORD-1042."
    return f"{action}. I still need the email address on the order."


def faq_reply(payload: dict) -> str:
    matches = payload.get("matches") or []
    if not matches:
        return ""
    return str(matches[0]["answer"])


def mismatch_reply(order_id: str | None) -> str:
    ref = f" for {order_id}" if order_id else ""
    return (
        f"I wasn't able to open an order{ref} with that email, so I don't have any details to share. "
        "Use the email from the confirmation and I can try again."
    )


def order_status_reply(payload: dict) -> str:
    order = payload["order"]
    name = str(order["customer_name"]).split()[0]
    items = items_with_prices(order["items"])
    prefix = ""
    open_return = payload.get("open_return")
    if open_return:
        prefix = (
            f"There's already an open return {open_return['id']} on {order['id']} from this chat. "
        )
    status = order["status"]
    if status == "shipped":
        return (
            f"{prefix}{name}, {order['id']} is on the way to {order['ship_to']}. {items}. "
            f"It shipped {format_date(order['shipped_at'])} with {order['carrier']}, "
            f"tracking {order['tracking']}. Estimated delivery {format_date(order['estimated_delivery'])}."
        )
    if status == "processing":
        return (
            f"{prefix}{name}, {order['id']} is processing and has not shipped yet. {items}. "
            f"Ordered {format_date(order['ordered_at'])}. You'll get tracking when it leaves the dock."
        )
    if status == "delivered":
        delivered = order["delivered_at"]
        window_days = int(payload["return_window_days"])
        end = window_end(delivered, window_days)
        days = int(payload.get("days_since_delivery") or 0)
        if days <= window_days:
            window = (
                f"The {window_days}-day return window is open through {format_date(end)}."
            )
        else:
            window = f"The {window_days}-day return window closed on {format_date(end)}."
        return (
            f"{prefix}{name}, {order['id']} was delivered to {order['ship_to']} on "
            f"{format_date(delivered)}. {items}. {window}"
        )
    if status == "returned":
        rma = order.get("existing_rma") or "an existing RMA"
        return (
            f"{prefix}{name}, {order['id']} ({item_names(order['items'])}) was already returned "
            f"under {rma}. I don't have a new shipment on that order."
        )
    return f"{prefix}{name}, {order['id']} is {status}. {items}."


def not_delivered_reply(payload: dict) -> str:
    order = payload["order"]
    if order["status"] == "shipped":
        return (
            f"{order['id']} hasn't been delivered yet, so there is nothing to return. "
            f"It shipped {format_date(order['shipped_at'])} with tracking {order['tracking']} "
            f"and is estimated for {format_date(order['estimated_delivery'])}. "
            "Once it arrives, I can start a return inside 30 days."
        )
    return (
        f"{order['id']} hasn't been delivered yet. It is still processing and has not shipped. "
        "There is nothing to return. If you want it cancelled, say so and I'll hand that to a person."
    )


def final_sale_reply(payload: dict) -> str:
    order = payload["order"]
    names = payload.get("item_names") or item_names(order["items"])
    count = len(payload.get("items") or order["items"])
    verb = "is" if count == 1 else "are"
    return (
        f"The {names} on {order['id']} {verb} final sale, so I can't start a return or an exchange. "
        "The product page and the packing slip both mark it that way."
    )


def already_returned_reply(payload: dict) -> str:
    order = payload["order"]
    rma = payload.get("rma") or order.get("existing_rma") or "an existing RMA"
    return (
        f"{order['id']} ({item_names(order['items'])}) was already returned under {rma}. "
        "I don't have a new shipment on that order."
    )


def ask_reason(payload: dict) -> str:
    order = payload["order"]
    window_days = int(payload["return_window_days"])
    return (
        f"{order['id']} ({item_names(order['items'])}) is inside the {window_days}-day return window "
        f"(delivered {format_date(order['delivered_at'])}). "
        "What's the reason: wrong size, changed your mind, or did it arrive damaged?"
    )


def return_created_reply(payload: dict) -> str:
    record = payload["return"]
    names = item_names(record["items"])
    extra = ""
    if record.get("reason") == "wrong_size":
        extra = (
            " If you want a different size, place a new order. "
            "This return covers the one that doesn't fit."
        )
    return (
        f"Return {record['id']} is open for {names} on {record['order_id']}. "
        f"Item total {money(record['item_total'])}. "
        f"A QR return label will be emailed to {record['email']}. "
        "Refunds go back to the original payment method after the dock checks the package in."
        + extra
    )


def customer_escalation_reply(ticket: dict) -> str:
    tid = ticket["id"]
    email = ticket.get("customer_email")
    follow = f" They'll follow up at {email}." if email else ""
    code = ticket.get("reason_code")
    facts = ticket.get("facts") or {}
    order_id = ticket.get("order_id")
    items = facts.get("item_names") or "that item"
    window_days = facts.get("return_window_days", 30)

    if code == "outside_window_exception":
        return (
            f"{order_id} ({items}) was delivered on {facts.get('delivered_on')}, "
            f"which is outside the {window_days}-day return window, so I can't start that return. "
            f"I opened {tid} for a teammate to decide on any exception.{follow}"
        )
    if code == "damage_claim":
        return (
            f"I'm sorry {items} arrived with a problem. I can't approve a damage claim from here. "
            f"A person needs to review it. I opened {tid} at high priority.{follow}"
        )
    if code == "worn_item":
        return (
            f"Because {items} was worn or washed, a person needs to inspect it before any refund. "
            f"I opened {tid}.{follow}"
        )
    if code == "customer_requested_human":
        if email:
            return f"I've handed this to a person. Ticket {tid} is on the queue.{follow}"
        return (
            f"I've handed this to a person. Ticket {tid} is on the queue. "
            "If you share the email on the order, they can pull it up before they write back."
        )
    if code == "legal_or_chargeback":
        return (
            "I'm not going to handle a chargeback or a legal question in this chat. "
            f"Ticket {tid} is flagged high priority for a person.{follow}"
        )
    if code == "order_not_found":
        return (
            f"I couldn't open an order with {order_id} and {email}. "
            f"I opened {tid} so a teammate can check systems I can't see. "
            "If the number or email is off, send the versions from your confirmation."
        )
    if code == "price_match":
        return (
            "Northline doesn't price-match other stores, and I can't make an exception from this desk. "
            f"I opened {tid} so a person can decide whether to do anything further."
        )
    if code == "no_faq_match":
        return (
            "I don't have that in the store FAQ, and I won't guess. "
            f"I opened {tid} for a person to answer."
        )
    if code == "cancellation":
        if facts.get("status") == "processing":
            return (
                f"{order_id} ({items}) is still processing and has not shipped. "
                f"I can't cancel it myself. Ticket {tid} asks a teammate to cancel it "
                f"if the dock hasn't packed it.{follow}"
            )
        status = facts.get("status") or "already moving"
        return (
            f"{order_id} is {status}, so I can't cancel it from here. "
            f"Ticket {tid} is with a teammate.{follow}"
        )
    if code == "agent_limit":
        return f"I couldn't finish that safely, so I opened {tid} for a person."
    return f"I opened {tid} so a person can take this from here.{follow}"
