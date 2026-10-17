import json

import pytest

from support_agent.agent import MAX_STEPS, SupportAgent
from support_agent.planner import (
    Action,
    OpenAIPlanner,
    PlannerConfigError,
    PlannerError,
    build_planner,
    resolve_mode,
)


def agent():
    return SupportAgent.create(mode="mock")


def test_shipping_faq_is_grounded_and_not_escalated():
    desk = agent()
    session = desk.new_session()
    result = desk.handle(session, "How long does standard shipping take?")
    assert result.escalated is False
    assert result.tools_used == ["search_faq"]
    assert "4-7 business days" in result.reply
    assert session.tickets == []


def test_tracking_question_uses_the_faq():
    desk = agent()
    session = desk.new_session()
    result = desk.handle(session, "How do I track an order?")
    assert result.tools_used == ["search_faq"]
    assert "Tracking is in your shipping email." in result.reply
    assert session.tickets == []


def test_order_lookup_and_multiturn_slots():
    desk = agent()
    session = desk.new_session()
    first = desk.handle(session, "Can you check my order?")
    assert "order number" in first.reply
    assert first.tools_used == []
    second = desk.handle(session, "It's ORD-1042 for ava.chen@northline.example")
    assert "NL-TRK-1042" in second.reply
    assert "Boulder" in second.reply
    assert second.escalated is False


def test_email_mismatch_does_not_leak_or_open_a_ticket():
    desk = agent()
    session = desk.new_session()
    result = desk.handle(session, "Status of ORD-1042 for thief@northline.example")
    assert result.escalated is False
    assert session.tickets == []
    for secret in ("Trailhead", "Ava", "Boulder", "NL-TRK-1042", "148"):
        assert secret not in result.reply


def test_standard_return_creates_an_rma_without_mutating_the_catalog():
    desk = agent()
    before = desk.catalog.order("ORD-1108")["status"]
    session = desk.new_session()
    asking = desk.handle(
        session,
        "I want to return ORD-1108. jules.okonkwo@northline.example",
    )
    assert "What's the reason" in asking.reply
    assert session.returns == []
    done = desk.handle(session, "It doesn't fit.")
    assert done.escalated is False
    assert session.returns[0]["id"] == "RMA-5001"
    assert "Cedar Wool Beanie" in done.reply
    assert desk.catalog.order("ORD-1108")["status"] == before


def test_worn_item_escalates_instead_of_auto_approving():
    desk = agent()
    session = desk.new_session()
    result = desk.handle(
        session,
        "I want to return ORD-1108. I already wore it. Email jules.okonkwo@northline.example",
    )
    assert session.returns == []
    assert session.tickets[0]["reason_code"] == "worn_item"
    assert "inspect" in result.reply


def test_later_request_does_not_keep_the_previous_order():
    desk = agent()
    session = desk.new_session()
    desk.handle(
        session,
        "I need to return the beanie from ORD-1108. It doesn't fit. Email jules.okonkwo@northline.example",
    )
    result = desk.handle(
        session,
        "I want a refund for ORD-0988. mina.park@northline.example. I changed my mind.",
    )
    assert result.escalated is True
    ticket = session.tickets[-1]
    assert ticket["order_id"] == "ORD-0988"
    assert ticket["reason_code"] == "outside_window_exception"
    assert "Ridgeline Down Parka" in ticket["summary"]
    assert "Beanie" not in ticket["summary"]
    assert "48 days" in ticket["summary"]


def test_sessions_do_not_share_tickets():
    desk = agent()
    first = desk.new_session()
    second = desk.new_session()
    desk.handle(first, "Let me talk to a real person.")
    assert len(first.tickets) == 1
    assert second.tickets == []


def test_tool_limit_opens_a_ticket():
    class LoopPlanner:
        model = None

        def next_action(self, session):
            return Action.tool("search_faq", {"query": "hello"})

    desk = SupportAgent.create(mode="scripted", planner=LoopPlanner())
    session = desk.new_session()
    result = desk.handle(session, "hello there, I need something odd")
    assert result.tools_used.count("search_faq") == MAX_STEPS
    assert session.tickets[0]["reason_code"] == "agent_limit"
    assert "couldn't finish" in result.reply


def test_mode_resolution(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SUPPORT_AGENT_MODE", raising=False)
    assert resolve_mode(None) == "mock"
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert resolve_mode(None) == "live"
    monkeypatch.setenv("SUPPORT_AGENT_MODE", "mock")
    assert resolve_mode(None) == "mock"
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(PlannerConfigError):
        build_planner("live")


class _Function:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, call_id, name, arguments):
        self.id = call_id
        self.function = _Function(name, arguments)


class _Message:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _Response:
    def __init__(self, message):
        self.choices = [type("Choice", (), {"message": message})()]


class _Completions:
    def __init__(self, messages):
        self._messages = list(messages)
        self.seen = []

    def create(self, **kwargs):
        self.seen.append(kwargs)
        return _Response(self._messages.pop(0))


class _Client:
    def __init__(self, messages):
        self.chat = type("Chat", (), {})()
        self.chat.completions = _Completions(messages)


def test_live_planner_runs_real_tools_with_a_fake_client():
    client = _Client(
        [
            _Message(
                tool_calls=[
                    _ToolCall(
                        "call_1",
                        "lookup_order",
                        json.dumps(
                            {
                                "order_id": "ORD-1042",
                                "email": "ava.chen@northline.example",
                            }
                        ),
                    )
                ]
            ),
            _Message(content="Your pack is on the way. Tracking NL-TRK-1042."),
        ]
    )
    planner = OpenAIPlanner(client=client, model="gpt-test", system_prompt_text="system")
    desk = SupportAgent.create(mode="scripted", planner=planner)
    session = desk.new_session()
    result = desk.handle(session, "Where is ORD-1042 for ava.chen@northline.example?")
    assert result.reply == "Your pack is on the way. Tracking NL-TRK-1042."
    assert result.tools_used == ["lookup_order"]
    assert session.tickets == []
    second = client.chat.completions.seen[1]
    assert second["model"] == "gpt-test"
    assert second["temperature"] == 0
    tool_messages = [message for message in second["messages"] if message["role"] == "tool"]
    assert "NL-TRK-1042" in tool_messages[0]["content"]


def test_empty_live_reply_is_an_error():
    client = _Client([_Message(content="  ")])
    planner = OpenAIPlanner(client=client, model="gpt-test", system_prompt_text="system")
    desk = SupportAgent.create(mode="scripted", planner=planner)
    with pytest.raises(PlannerError):
        desk.handle(desk.new_session(), "hello")
