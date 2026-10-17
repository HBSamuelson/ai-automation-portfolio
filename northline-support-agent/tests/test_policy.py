from support_agent.policy import classify_message, extract_slots


def test_policy_questions_stay_out_of_the_return_flow():
    assert classify_message("What's your return policy?") == "faq"
    assert classify_message("How do I track an order?") == "faq"
    assert classify_message("How long does standard shipping take?") == "faq"


def test_action_intents():
    assert classify_message("I want to return ORD-1108") == "return"
    assert classify_message("Can you check my order?") == "order"
    assert classify_message("Let me talk to a real person.") == "human"
    assert classify_message("Please cancel ORD-1302") == "cancel"
    assert classify_message("The lamp arrived damaged") == "damage"
    assert classify_message("Can you price match a competitor?") == "price_match"
    assert classify_message("I will file a chargeback and call my lawyer if you don't refund me.") == "legal"


def test_slot_fill_keeps_the_open_request():
    assert classify_message("It's ORD-1042 for ava.chen@northline.example") == "ambiguous"
    assert classify_message("wrong size") == "ambiguous"
    assert classify_message("I changed my mind") == "ambiguous"


def test_latest_request_drops_the_previous_order():
    messages = [
        {"role": "user", "content": "I need to return the beanie from ORD-1108. It doesn't fit. Email jules.okonkwo@northline.example"},
        {"role": "assistant", "content": "Return opened."},
        {"role": "user", "content": "I want a refund for ORD-0988. mina.park@northline.example. I changed my mind."},
    ]
    slots = extract_slots(messages)
    assert slots.order_id == "ORD-0988"
    assert slots.email == "mina.park@northline.example"
    assert slots.reason == "changed_mind"
