"""Desk tools. Policy lives here, not in the model's wording.

An email that does not match an order returns the same shape as a miss:
no line items, no address, no status, no customer name.
"""

from __future__ import annotations

import re
from typing import Protocol

from support_agent.catalog import Catalog
from support_agent.policy import (
    Slots,
    days_since,
    extract_slots,
    folded,
    format_date,
    item_names,
    label_for,
    last_user_text,
    money,
    priority_for,
    recommended_for,
    request_texts,
    user_texts,
    with_args,
)

RETURN_LABELS = {
    "wrong_size": "Wrong size",
    "changed_mind": "Changed mind",
    "damaged": "Damaged",
    "missing": "Missing item",
    "worn": "Worn or washed",
    "unspecified": "Not specified",
}


class DeskSession(Protocol):
    messages: list[dict]
    tickets: list[dict]
    returns: list[dict]
    ticket_seq: int
    return_seq: int


def execute(name: str, args: dict, session: DeskSession, catalog: Catalog) -> dict:
    slots = with_args(extract_slots(session.messages), args or {})
    if name == "search_faq":
        query = str((args or {}).get("query") or last_user_text(session.messages))
        return search_faq(catalog, query)
    if name == "lookup_order":
        return lookup_order(catalog, slots, session)
    if name == "check_return_eligibility":
        return check_return_eligibility(catalog, slots, session)
    if name == "create_return":
        return create_return(catalog, slots, session)
    if name == "escalate_to_human":
        reason = str((args or {}).get("reason_code") or "").strip()
        if not reason:
            return {"ok": False, "error": "missing_fields", "missing": ["reason_code"], "code": "missing_fields"}
        return escalate_to_human(catalog, slots, session, reason)
    return {"ok": False, "error": "unknown_tool", "name": name}


def search_faq(catalog: Catalog, query: str) -> dict:
    query_folded = folded(query)
    tokens = set(re.findall(r"[a-z0-9]+", query_folded))
    scored: list[tuple[int, str, dict]] = []
    for faq in catalog.faqs:
        score = 0
        for phrase in faq.get("phrases", []):
            if _phrase_hit(str(phrase), query_folded):
                score += 5
        if score < 5:
            continue
        for keyword in faq.get("keywords", []):
            if str(keyword) in tokens:
                score += 1
        scored.append((score, str(faq["id"]), faq))
    scored.sort(key=lambda row: (-row[0], row[1]))
    matches = [
        {"id": faq["id"], "question": faq["question"], "answer": faq["answer"]}
        for _, _, faq in scored[:3]
    ]
    return {"ok": True, "query": query, "matches": matches}


def lookup_order(catalog: Catalog, slots: Slots, session: DeskSession) -> dict:
    missing = _missing(slots)
    if missing:
        return _missing_payload(missing)
    order = catalog.order(slots.order_id)
    if order is None:
        return {
            "ok": True,
            "found": False,
            "reason": "not_found",
            "order_id": slots.order_id,
            "email": slots.email,
        }
    if order["email"].lower() != slots.email.lower():
        # Do not attach the real order. The caller cannot tell a mismatch
        # from a made-up id by reading item data.
        return {
            "ok": True,
            "found": False,
            "reason": "email_mismatch",
            "order_id": slots.order_id,
        }
    payload: dict = {
        "ok": True,
        "found": True,
        "reason": "found",
        "order": _public_order(order),
        "as_of": catalog.as_of.isoformat(),
        "return_window_days": catalog.return_window_days,
    }
    if order.get("delivered_at"):
        payload["days_since_delivery"] = days_since(order["delivered_at"], catalog.as_of)
    open_return = _session_return(session, order["id"])
    if open_return:
        payload["open_return"] = {
            "id": open_return["id"],
            "reason": open_return["reason"],
            "item_total": open_return["item_total"],
        }
    return payload


def check_return_eligibility(catalog: Catalog, slots: Slots, session: DeskSession) -> dict:
    missing = _missing(slots)
    if missing:
        return _missing_payload(missing)
    order = catalog.order(slots.order_id)
    if order is None:
        return {"ok": True, "code": "not_found", "order_id": slots.order_id, "email": slots.email, "eligible": False}
    if order["email"].lower() != slots.email.lower():
        return {
            "ok": True,
            "code": "email_mismatch",
            "order_id": slots.order_id,
            "eligible": False,
            "auto_approve": False,
        }
    text = " ".join(request_texts(session.messages))
    return assess_order(order, slots, catalog, session.returns, text)


def assess_order(
    order: dict,
    slots: Slots,
    catalog: Catalog,
    session_returns: list[dict],
    request_text: str,
) -> dict:
    """Pure return decision for one verified order."""
    existing = next((row for row in session_returns if row["order_id"] == order["id"]), None)
    if existing:
        return _decision(
            "already_returned",
            order,
            catalog,
            rma=existing["id"],
            item_names=item_names(existing["items"]),
        )
    if order["status"] == "returned" or order.get("existing_rma"):
        return _decision("already_returned", order, catalog, rma=order.get("existing_rma"))
    if order["status"] != "delivered":
        return _decision("not_delivered", order, catalog)

    chosen = _select_items(order, request_text)
    returnable = [item for item in chosen if not item["final_sale"]]
    if not returnable:
        blocked = [item for item in chosen if item["final_sale"]] or chosen
        return _decision("final_sale", order, catalog, items=blocked, item_names=item_names(blocked))

    reason = slots.reason
    if reason in {"damaged", "missing"}:
        return _decision("damage_review", order, catalog, items=returnable, reason=reason)
    if reason == "worn":
        return _decision("worn_review", order, catalog, items=returnable, reason=reason)

    delivered = order["delivered_at"]
    age = days_since(delivered, catalog.as_of)
    if age > catalog.return_window_days:
        return _decision(
            "outside_window",
            order,
            catalog,
            items=returnable,
            reason=reason,
            days_since_delivery=age,
        )
    if reason == "unspecified":
        return _decision("need_reason", order, catalog, items=returnable, days_since_delivery=age)
    return _decision(
        "eligible",
        order,
        catalog,
        items=returnable,
        reason=reason,
        days_since_delivery=age,
    )


def create_return(catalog: Catalog, slots: Slots, session: DeskSession) -> dict:
    decision = check_return_eligibility(catalog, slots, session)
    if decision.get("code") != "eligible":
        return {
            "ok": False,
            "created": False,
            "code": decision.get("code"),
            "explanation": "That order is not eligible for an automatic return.",
        }
    order = catalog.order(slots.order_id)
    assert order is not None
    items = decision.get("items") or []
    total = round(sum(float(item["price"]) * int(item["qty"]) for item in items), 2)
    record = {
        "id": f"RMA-{session.return_seq}",
        "order_id": order["id"],
        "email": order["email"],
        "reason": slots.reason,
        "reason_label": RETURN_LABELS.get(slots.reason, slots.reason),
        "items": [
            {
                "sku": item["sku"],
                "name": item["name"],
                "qty": item["qty"],
                "price": item["price"],
            }
            for item in items
        ],
        "item_total": total,
        "created_on": catalog.as_of.isoformat(),
    }
    session.return_seq += 1
    session.returns.append(record)
    return {"ok": True, "created": True, "return": record}


def escalate_to_human(catalog: Catalog, slots: Slots, session: DeskSession, reason_code: str) -> dict:
    order = _matched_order(catalog, slots)
    facts = _facts(order, catalog) if order else None
    quotes = "\n".join(user_texts(session.messages))[:600]
    summary = _summary(reason_code, slots, facts, quotes, catalog)
    ticket = {
        "id": f"TCK-{session.ticket_seq}",
        "priority": priority_for(reason_code),
        "reason_code": reason_code,
        "reason_label": label_for(reason_code),
        "summary": summary,
        "recommended_action": recommended_for(reason_code),
        "customer_email": slots.email,
        "order_id": slots.order_id,
        "quotes": quotes,
        "facts": facts,
    }
    session.ticket_seq += 1
    session.tickets.append(ticket)
    return {"ok": True, "created": True, "ticket": ticket}


def _summary(
    reason_code: str,
    slots: Slots,
    facts: dict | None,
    quotes: str,
    catalog: Catalog,
) -> str:
    email = slots.email or "no email given"
    order_id = slots.order_id or "no order number"
    latest = _quote_last(quotes)
    if reason_code == "outside_window_exception" and facts:
        reason = slots.reason.replace("_", " ")
        return (
            f"Customer asked to return {order_id} ({facts['item_names']}, {facts['item_total']}), "
            f"delivered {facts['delivered_on']} ({facts['days_since_delivery']} days before the desk date "
            f"{format_date(catalog.as_of)}). Email {email}. Reason: {reason}. "
            f"The {catalog.return_window_days}-day window has closed."
        )
    if reason_code == "damage_claim" and facts:
        delivered = facts.get("delivered_on", "an unknown date")
        return (
            f"Customer reports a problem with {facts['item_names']} on {order_id}. "
            f"Email {email}. Delivered {delivered}. Item total {facts['item_total']}. "
            "Needs a person to review before any replacement or refund."
        )
    if reason_code == "worn_item" and facts:
        return (
            f"Customer wants help with {facts['item_names']} on {order_id} and says it was worn or washed. "
            f"Email {email}. Item total {facts['item_total']}."
        )
    if reason_code == "cancellation" and facts:
        ordered = facts.get("ordered_on", "an unknown date")
        return (
            f"Customer asked to cancel {order_id} ({facts['item_names']}, {facts['item_total']}). "
            f"Status: {facts['status']}. Ordered {ordered}. Email {email}."
        )
    if reason_code == "customer_requested_human":
        verified = f"Verified order {order_id}. " if facts else "No order was verified in this chat. "
        return f"Customer asked for a person. {verified}Latest message: {latest}"
    if reason_code == "legal_or_chargeback":
        return (
            "Customer mentioned a chargeback or legal action. No refund was issued. "
            f"Latest message: {latest}"
        )
    if reason_code == "order_not_found":
        return (
            f"Lookup failed for {order_id} and {email}. "
            "Nothing else was revealed because no order matched."
        )
    if reason_code == "price_match":
        return (
            "Customer asked for a price match against another store. "
            "Northline has no price-match policy in the FAQ. No order was changed. "
            f"Latest message: {latest}"
        )
    if reason_code == "no_faq_match":
        return f"No FAQ entry matched. Customer said: {latest}"
    if reason_code == "agent_limit":
        return "The agent hit its tool limit. Transcript is attached. No action was taken on the order."
    return f"Escalated ({reason_code}) for {email}. Order {order_id}."


def _facts(order: dict, catalog: Catalog) -> dict:
    total = round(sum(float(item["price"]) * int(item["qty"]) for item in order["items"]), 2)
    facts: dict = {
        "item_names": item_names(order["items"]),
        "item_total": money(total),
        "status": order["status"],
        "customer_name": order["customer_name"],
        "ship_to": order["ship_to"],
        "return_window_days": catalog.return_window_days,
    }
    if order.get("delivered_at"):
        facts["delivered_on"] = format_date(order["delivered_at"])
        facts["days_since_delivery"] = days_since(order["delivered_at"], catalog.as_of)
    if order.get("ordered_at"):
        facts["ordered_on"] = format_date(order["ordered_at"])
    if order.get("existing_rma"):
        facts["existing_rma"] = order["existing_rma"]
    return facts


def _matched_order(catalog: Catalog, slots: Slots) -> dict | None:
    order = catalog.order(slots.order_id)
    if order is None or not slots.email:
        return None
    if order["email"].lower() != slots.email.lower():
        return None
    return order


def _decision(code: str, order: dict, catalog: Catalog, **extra: object) -> dict:
    payload: dict = {
        "ok": True,
        "code": code,
        "order_id": order["id"],
        "eligible": code == "eligible",
        "auto_approve": code == "eligible",
        "order": _public_order(order),
        "return_window_days": catalog.return_window_days,
        "as_of": catalog.as_of.isoformat(),
    }
    if order.get("delivered_at"):
        payload["days_since_delivery"] = days_since(order["delivered_at"], catalog.as_of)
    payload.update(extra)
    return payload


def _public_order(order: dict) -> dict:
    return {
        "id": order["id"],
        "customer_name": order["customer_name"],
        "email": order["email"],
        "status": order["status"],
        "ordered_at": order["ordered_at"],
        "shipped_at": order["shipped_at"],
        "delivered_at": order["delivered_at"],
        "estimated_delivery": order["estimated_delivery"],
        "carrier": order["carrier"],
        "tracking": order["tracking"],
        "ship_to": order["ship_to"],
        "existing_rma": order.get("existing_rma"),
        "items": [
            {
                "sku": item["sku"],
                "name": item["name"],
                "qty": item["qty"],
                "price": item["price"],
                "final_sale": item["final_sale"],
            }
            for item in order["items"]
        ],
    }


def _select_items(order: dict, text: str) -> list[dict]:
    query = folded(text)
    hits = []
    for item in order["items"]:
        name = str(item["name"]).lower()
        if name in query:
            hits.append(item)
            continue
        words = [word for word in re.findall(r"[a-z0-9]+", name) if len(word) > 4]
        if any(word in query for word in words):
            hits.append(item)
    return hits or list(order["items"])


def _session_return(session: DeskSession, order_id: str) -> dict | None:
    for record in session.returns:
        if record["order_id"] == order_id:
            return record
    return None


def _missing(slots: Slots) -> list[str]:
    missing = []
    if not slots.order_id:
        missing.append("order_id")
    if not slots.email:
        missing.append("email")
    return missing


def _missing_payload(missing: list[str]) -> dict:
    return {"ok": False, "error": "missing_fields", "missing": missing, "code": "missing_fields"}


def _phrase_hit(phrase: str, query_folded: str) -> bool:
    needle = folded(phrase)
    if " " in needle or len(needle) > 4:
        return needle in query_folded
    return re.search(rf"\b{re.escape(needle)}\b", query_folded) is not None


def _quote_last(quotes: str) -> str:
    lines = [line.strip() for line in quotes.splitlines() if line.strip()]
    text = lines[-1] if lines else ""
    if len(text) > 300:
        text = text[:297] + "..."
    return f'"{text}"'
