"""Tool loop shared by the CLI, the web desk, and the eval."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from uuid import uuid4

from support_agent.catalog import Catalog
from support_agent.planner import Action, PlannerError, build_planner, resolve_mode
from support_agent.policy import classify_message, extract_slots
from support_agent.replies import customer_escalation_reply
from support_agent.tools import execute

MAX_STEPS = 5


@dataclass
class Session:
    id: str
    messages: list[dict] = field(default_factory=list)
    tickets: list[dict] = field(default_factory=list)
    returns: list[dict] = field(default_factory=list)
    goal: str | None = None
    ticket_seq: int = 1001
    return_seq: int = 5001
    tool_seq: int = 1


@dataclass
class TurnResult:
    reply: str
    escalated: bool
    tools_used: list[str]
    tickets: list[dict]
    returns: list[dict]


class SupportAgent:
    def __init__(self, catalog: Catalog, planner, mode: str):
        self.catalog = catalog
        self.planner = planner
        self.mode = mode

    @classmethod
    def create(cls, mode: str | None = None, planner=None) -> SupportAgent:
        catalog = Catalog.load()
        if planner is None:
            resolved = resolve_mode(mode)
            planner = build_planner(resolved, catalog)
        else:
            resolved = mode or "scripted"
        return cls(catalog=catalog, planner=planner, mode=resolved)

    @property
    def model_name(self) -> str | None:
        return getattr(self.planner, "model", None)

    def new_session(self) -> Session:
        return Session(id=uuid4().hex[:12])

    def handle(self, session: Session, user_text: str) -> TurnResult:
        text = user_text.strip()
        if not text:
            raise ValueError("Message is empty.")
        tickets_before = len(session.tickets)
        session.messages.append({"role": "user", "content": text})
        _update_goal(session, text)
        tools_used: list[str] = []
        for _ in range(MAX_STEPS):
            action = self.planner.next_action(session)
            if action.kind == "message":
                reply = action.text.strip()
                session.messages.append({"role": "assistant", "content": reply})
                return _result(session, reply, tools_used, tickets_before)
            _run_tools(self, session, action, tools_used)
        return _stop_at_limit(self, session, tools_used, tickets_before)


def _update_goal(session: Session, text: str) -> None:
    intent = classify_message(text)
    if intent == "ambiguous":
        if session.goal is None:
            slots = extract_slots([{"role": "user", "content": text}])
            session.goal = "order" if slots.order_id or slots.email else "faq"
        return
    session.goal = intent


def _run_tools(agent: SupportAgent, session: Session, action: Action, tools_used: list[str]) -> None:
    calls = []
    results = []
    for call in action.calls:
        call_id = call.id or f"call_{session.id}_{session.tool_seq}"
        session.tool_seq += 1
        payload = execute(call.name, call.arguments, session, agent.catalog)
        tools_used.append(call.name)
        calls.append({"id": call_id, "name": call.name, "arguments": call.arguments})
        results.append((call_id, call.name, payload))
    session.messages.append({"role": "assistant", "content": "", "tool_calls": calls})
    for call_id, name, payload in results:
        session.messages.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "name": name,
                "content": json.dumps(payload),
            }
        )


def _stop_at_limit(
    agent: SupportAgent,
    session: Session,
    tools_used: list[str],
    tickets_before: int,
) -> TurnResult:
    if len(session.tickets) == tickets_before:
        payload = execute("escalate_to_human", {"reason_code": "agent_limit"}, session, agent.catalog)
        tools_used.append("escalate_to_human")
        session.messages.append(
            {
                "role": "tool",
                "tool_call_id": f"call_{session.id}_{session.tool_seq}",
                "name": "escalate_to_human",
                "content": json.dumps(payload),
            }
        )
        session.tool_seq += 1
    ticket = session.tickets[-1]
    reply = customer_escalation_reply(ticket)
    session.messages.append({"role": "assistant", "content": reply})
    return _result(session, reply, tools_used, tickets_before)


def _result(
    session: Session,
    reply: str,
    tools_used: list[str],
    tickets_before: int,
) -> TurnResult:
    return TurnResult(
        reply=reply,
        escalated=len(session.tickets) > tickets_before,
        tools_used=tools_used,
        tickets=list(session.tickets),
        returns=list(session.returns),
    )


__all__ = ["PlannerError", "Session", "SupportAgent", "TurnResult", "MAX_STEPS"]
