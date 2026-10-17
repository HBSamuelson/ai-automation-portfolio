import copy
import json
from datetime import timedelta

from support_agent.agent import SupportAgent
from support_agent.catalog import Catalog
from support_agent.policy import Slots
from support_agent.tools import assess_order, execute, search_faq


def test_faq_search_picks_the_shipping_answer():
    catalog = Catalog.load()
    result = search_faq(catalog, "How long does standard shipping take?")
    assert result["matches"][0]["id"] == "shipping_times"
    assert "4-7 business days" in result["matches"][0]["answer"]


def test_faq_search_misses_unknown_products():
    catalog = Catalog.load()
    result = search_faq(catalog, "Do you sell kayaks or book guided trips?")
    assert result["matches"] == []


def test_email_mismatch_hides_the_order():
    agent = SupportAgent.create(mode="mock")
    session = agent.new_session()
    payload = execute(
        "lookup_order",
        {"order_id": "ORD-1042", "email": "thief@northline.example"},
        session,
        agent.catalog,
    )
    encoded = json.dumps(payload)
    assert payload["found"] is False
    assert payload["reason"] == "email_mismatch"
    assert "order" not in payload
    for secret in ("Trailhead", "Ava", "Boulder", "NL-TRK-1042", "148"):
        assert secret not in encoded


def test_return_window_boundary():
    catalog = Catalog.load()
    order = copy.deepcopy(catalog.order("ORD-1108"))
    slots = Slots(order_id=order["id"], email=order["email"], reason="wrong_size")
    order["delivered_at"] = (catalog.as_of - timedelta(days=30)).isoformat()
    inside = assess_order(order, slots, catalog, [], "wrong size")
    order["delivered_at"] = (catalog.as_of - timedelta(days=31)).isoformat()
    outside = assess_order(order, slots, catalog, [], "wrong size")
    assert inside["code"] == "eligible"
    assert outside["code"] == "outside_window"


def test_priority_comes_from_policy_not_the_caller():
    agent = SupportAgent.create(mode="mock")
    session = agent.new_session()
    session.messages.append({"role": "user", "content": "I am calling my lawyer."})
    payload = execute(
        "escalate_to_human",
        {"reason_code": "legal_or_chargeback", "priority": "low"},
        session,
        agent.catalog,
    )
    assert payload["ticket"]["priority"] == "high"


def test_not_found_ticket_does_not_attach_a_real_order():
    agent = SupportAgent.create(mode="mock")
    session = agent.new_session()
    session.messages.append(
        {"role": "user", "content": "Look up ORD-1042 for ghost@northline.example"}
    )
    payload = execute(
        "escalate_to_human",
        {"reason_code": "order_not_found", "order_id": "ORD-1042", "email": "ghost@northline.example"},
        session,
        agent.catalog,
    )
    encoded = json.dumps(payload)
    for secret in ("Trailhead", "Ava", "Boulder", "NL-TRK-1042"):
        assert secret not in encoded
