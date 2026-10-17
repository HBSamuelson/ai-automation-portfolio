"""Planners that choose the next tool call or the customer reply.

The mock planner is deterministic and is what the eval measures.
The live planner speaks the OpenAI chat-completions tool protocol.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from support_agent.catalog import Catalog
from support_agent.policy import extract_slots, last_user_text
from support_agent.replies import (
    GREETING,
    already_returned_reply,
    ask_for_identity,
    ask_reason,
    customer_escalation_reply,
    faq_reply,
    final_sale_reply,
    mismatch_reply,
    not_delivered_reply,
    order_status_reply,
    return_created_reply,
)

TOOL_SPECS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_faq",
            "description": "Search Northline FAQ entries. Use for policy questions. Do not invent an answer when this returns no matches.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_order",
            "description": "Look up an order. Requires the order id and the email on the order. A mismatch returns no order details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "email": {"type": "string"},
                },
                "required": ["order_id", "email"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_return_eligibility",
            "description": "Check whether an order can be returned automatically. Call this before create_return.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "email": {"type": "string"},
                    "reason": {
                        "type": "string",
                        "description": "wrong_size, changed_mind, damaged, missing, worn, or unspecified",
                    },
                },
                "required": ["order_id", "email"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_return",
            "description": "Open an RMA. Only succeeds when check_return_eligibility says the order is eligible.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "email": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["order_id", "email"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": (
                "Open a human ticket. Use reason_code: outside_window_exception, damage_claim, "
                "worn_item, customer_requested_human, legal_or_chargeback, order_not_found, "
                "price_match, cancellation, no_faq_match, or agent_limit. "
                "The ticket summary is built from tool data. Call this before telling the customer a person has it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason_code": {"type": "string"},
                    "order_id": {"type": "string"},
                    "email": {"type": "string"},
                },
                "required": ["reason_code"],
                "additionalProperties": False,
            },
        },
    },
]


class PlannerError(RuntimeError):
    """The live planner could not produce a usable action."""


class PlannerConfigError(RuntimeError):
    """Live mode was requested without enough configuration."""


@dataclass
class ToolCall:
    name: str
    arguments: dict
    id: str | None = None


@dataclass
class Action:
    kind: str
    text: str = ""
    calls: list[ToolCall] = field(default_factory=list)

    @staticmethod
    def message(text: str) -> Action:
        return Action(kind="message", text=text)

    @staticmethod
    def tool(name: str, arguments: dict | None = None) -> Action:
        return Action(kind="tools", calls=[ToolCall(name=name, arguments=arguments or {})])


def resolve_mode(mode: str | None = None) -> str:
    if mode in {"mock", "live"}:
        return mode
    if mode not in {None, ""}:
        raise PlannerConfigError(f"Unknown mode {mode!r}. Use mock or live.")
    env = os.environ.get("SUPPORT_AGENT_MODE", "").strip().lower()
    if env in {"mock", "live"}:
        return env
    if env:
        raise PlannerConfigError(f"Unknown SUPPORT_AGENT_MODE {env!r}. Use mock or live.")
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return "live"
    return "mock"


def build_planner(mode: str | None = None, catalog: Catalog | None = None):
    resolved = resolve_mode(mode)
    if resolved == "mock":
        return MockPlanner()
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise PlannerConfigError(
            "OPENAI_API_KEY is not set. Start with --mock, or export a key for live mode."
        )
    store = catalog or Catalog.load()
    return OpenAIPlanner.from_env(store)


def system_prompt(catalog: Catalog) -> str:
    return (
        f"You are the customer-support agent for {catalog.store_name}, a fictional outdoor shop. "
        f"The desk date is {catalog.as_of.isoformat()}. "
        f"The return window is {catalog.return_window_days} days from delivery.\n\n"
        "Use tools for anything about a specific order, return, or policy. "
        "Do not invent order status, tracking numbers, refunds, or policies.\n\n"
        "Resolve on your own when a tool gives a clear result:\n"
        "- FAQ answers come from search_faq. If it returns no match, escalate with reason_code no_faq_match.\n"
        "- Order status comes from lookup_order. If the email does not match, say you cannot open the order "
        "and do not guess what is in it. Do not escalate email mismatches.\n"
        "- If the order id is not found, escalate with reason_code order_not_found.\n"
        "- Standard returns: check_return_eligibility, then create_return only when auto_approve is true.\n"
        "- If eligibility code is outside_window, escalate with outside_window_exception.\n"
        "- Damage, a missing item, or a worn or washed item escalates. Do not create a return for those.\n"
        "- Final-sale and not-yet-delivered results are final. Explain them. Do not escalate those.\n"
        "- Cancellations escalate with cancellation after you have looked the order up.\n"
        "- Price-match requests escalate with price_match.\n"
        "- If the customer asks for a person, escalate with customer_requested_human.\n"
        "- Chargebacks, lawyers, lawsuits, or complaint boards escalate with legal_or_chargeback. "
        "Do not argue and do not refund.\n\n"
        "When you escalate, call escalate_to_human before you tell the customer, and include the ticket id "
        "from the tool in your reply. Ask for the order number and email when you need them. "
        "Keep replies short and specific."
    )


class MockPlanner:
    """Rule planner. It calls the same tools a live model would."""

    model = None

    def next_action(self, session) -> Action:
        recent = _since_last_user(session.messages)
        tool_messages = [message for message in recent if message.get("role") == "tool"]
        if tool_messages:
            last = tool_messages[-1]
            payload = json.loads(last["content"])
            return self._after(session, last.get("name", ""), payload)
        return self._before(session)

    def _before(self, session) -> Action:
        slots = extract_slots(session.messages)
        goal = session.goal or "faq"
        if goal == "greeting":
            return Action.message(GREETING)
        if goal == "human":
            return Action.tool("escalate_to_human", {"reason_code": "customer_requested_human"})
        if goal == "legal":
            return Action.tool("escalate_to_human", {"reason_code": "legal_or_chargeback"})
        if goal == "price_match":
            return Action.tool("escalate_to_human", {"reason_code": "price_match"})
        if goal in {"order", "damage", "cancel", "return"} and (not slots.order_id or not slots.email):
            return Action.message(ask_for_identity(goal, slots))
        if goal in {"order", "damage", "cancel"}:
            return Action.tool("lookup_order", {})
        if goal == "return":
            return Action.tool("check_return_eligibility", {})
        if goal == "faq":
            return Action.tool("search_faq", {"query": last_user_text(session.messages)})
        return Action.message(GREETING)

    def _after(self, session, name: str, payload: dict) -> Action:
        if payload.get("code") == "missing_fields" or payload.get("error") == "missing_fields":
            return Action.message(ask_for_identity(session.goal or "order", extract_slots(session.messages)))
        if name == "search_faq":
            if payload.get("matches"):
                return Action.message(faq_reply(payload))
            return Action.tool("escalate_to_human", {"reason_code": "no_faq_match"})
        if name == "lookup_order":
            return self._after_lookup(session, payload)
        if name == "check_return_eligibility":
            return _after_eligibility(payload)
        if name == "create_return":
            if not payload.get("created"):
                return Action.message(
                    "I couldn't start that return. "
                    + (payload.get("explanation") or "Check the order number and email.")
                )
            return Action.message(return_created_reply(payload))
        if name == "escalate_to_human":
            ticket = payload.get("ticket") or {}
            return Action.message(customer_escalation_reply(ticket))
        return Action.message("I hit something I can't finish. Say if you want a person.")

    def _after_lookup(self, session, payload: dict) -> Action:
        if not payload.get("found"):
            if payload.get("reason") == "email_mismatch":
                return Action.message(mismatch_reply(payload.get("order_id")))
            return Action.tool("escalate_to_human", {"reason_code": "order_not_found"})
        if session.goal == "damage":
            return Action.tool("escalate_to_human", {"reason_code": "damage_claim"})
        if session.goal == "cancel":
            return Action.tool("escalate_to_human", {"reason_code": "cancellation"})
        return Action.message(order_status_reply(payload))


def _after_eligibility(payload: dict) -> Action:
    code = payload.get("code")
    if code == "eligible":
        return Action.tool("create_return", {})
    if code == "need_reason":
        return Action.message(ask_reason(payload))
    if code == "outside_window":
        return Action.tool("escalate_to_human", {"reason_code": "outside_window_exception"})
    if code == "damage_review":
        return Action.tool("escalate_to_human", {"reason_code": "damage_claim"})
    if code == "worn_review":
        return Action.tool("escalate_to_human", {"reason_code": "worn_item"})
    if code == "email_mismatch":
        return Action.message(mismatch_reply(payload.get("order_id")))
    if code == "not_found":
        return Action.tool("escalate_to_human", {"reason_code": "order_not_found"})
    if code == "final_sale":
        return Action.message(final_sale_reply(payload))
    if code == "not_delivered":
        return Action.message(not_delivered_reply(payload))
    if code == "already_returned":
        return Action.message(already_returned_reply(payload))
    return Action.message("I couldn't check that return. Send the order number and email again.")


def _since_last_user(messages: list[dict]) -> list[dict]:
    recent: list[dict] = []
    for message in reversed(messages):
        if message.get("role") == "user":
            break
        recent.append(message)
    recent.reverse()
    return recent


class OpenAIPlanner:
    """OpenAI-compatible tool caller. Client is injectable for tests."""

    def __init__(self, client, model: str, system_prompt_text: str):
        self.client = client
        self.model = model
        self.system_prompt_text = system_prompt_text

    @classmethod
    def from_env(cls, catalog: Catalog) -> OpenAIPlanner:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise PlannerConfigError("Install the openai package to use live mode.") from exc
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        base = os.environ.get("OPENAI_BASE_URL", "").strip() or None
        model = os.environ.get("OPENAI_MODEL", "").strip() or "gpt-4o-mini"
        client = OpenAI(api_key=key, base_url=base)
        return cls(client=client, model=model, system_prompt_text=system_prompt(catalog))

    def next_action(self, session) -> Action:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=to_openai_messages(session.messages, self.system_prompt_text),
                tools=TOOL_SPECS,
                tool_choice="auto",
            )
        except PlannerError:
            raise
        except Exception as exc:
            raise PlannerError(f"The model API request failed: {exc}") from exc
        try:
            message = response.choices[0].message
        except (AttributeError, IndexError, KeyError) as exc:
            raise PlannerError("The model API returned no message.") from exc
        return action_from_message(message)


def to_openai_messages(messages: list[dict], prompt: str) -> list[dict]:
    converted = [{"role": "system", "content": prompt}]
    for message in messages:
        role = message.get("role")
        if role == "user":
            converted.append({"role": "user", "content": message.get("content") or ""})
        elif role == "assistant":
            calls = message.get("tool_calls") or []
            if calls:
                converted.append(
                    {
                        "role": "assistant",
                        "content": message.get("content") or None,
                        "tool_calls": [
                            {
                                "id": call["id"],
                                "type": "function",
                                "function": {
                                    "name": call["name"],
                                    "arguments": json.dumps(call["arguments"]),
                                },
                            }
                            for call in calls
                        ],
                    }
                )
            else:
                converted.append({"role": "assistant", "content": message.get("content") or ""})
        elif role == "tool":
            converted.append(
                {
                    "role": "tool",
                    "tool_call_id": message["tool_call_id"],
                    "content": message["content"],
                }
            )
    return converted


def action_from_message(message) -> Action:
    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        calls = []
        for tool_call in tool_calls:
            name = tool_call.function.name
            raw = tool_call.function.arguments or "{}"
            try:
                arguments = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise PlannerError(f"Model returned invalid tool arguments for {name}.") from exc
            if not isinstance(arguments, dict):
                raise PlannerError(f"Tool arguments for {name} were not an object.")
            calls.append(ToolCall(id=tool_call.id, name=name, arguments=arguments))
        return Action(kind="tools", calls=calls)
    content = (getattr(message, "content", None) or "").strip()
    if not content:
        raise PlannerError("Model returned an empty reply.")
    return Action(kind="message", text=content)
