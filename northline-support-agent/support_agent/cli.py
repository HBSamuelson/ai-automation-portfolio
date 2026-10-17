"""Command-line desk for Northline support."""

from __future__ import annotations

import argparse
import sys

from support_agent.agent import SupportAgent
from support_agent.planner import PlannerConfigError, PlannerError
from support_agent.policy import item_names, money

INTRO = "Northline desk. Fictional shop, mock orders. /quit to leave, /reset to start over."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Talk to the Northline Supply support agent.")
    parser.add_argument(
        "messages",
        nargs="*",
        help="Customer messages, in order. Omit them for an interactive chat.",
    )
    parser.add_argument("--mock", action="store_true", help="Force the offline planner.")
    parser.add_argument("--live", action="store_true", help="Force the OpenAI-compatible planner.")
    args = parser.parse_args(argv)
    if args.mock and args.live:
        print("Choose either --mock or --live.", file=sys.stderr)
        return 2
    mode = "mock" if args.mock else "live" if args.live else None
    try:
        agent = SupportAgent.create(mode=mode)
    except PlannerConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    session = agent.new_session()
    seen_returns = 0
    seen_tickets = 0

    def turn(message: str) -> int:
        nonlocal seen_returns, seen_tickets
        try:
            result = agent.handle(session, message)
        except PlannerError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"You: {message}\n")
        print(f"Agent: {result.reply}\n")
        for record in result.returns[seen_returns:]:
            print(_render_return(record))
            print()
        for ticket in result.tickets[seen_tickets:]:
            print(_render_ticket(ticket))
            print()
        seen_returns = len(result.returns)
        seen_tickets = len(result.tickets)
        return 0

    if args.messages:
        for message in args.messages:
            code = turn(message)
            if code:
                return code
        return 0

    print(INTRO)
    while True:
        try:
            message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not message:
            continue
        if message in {"/quit", "/exit", "quit", "exit"}:
            return 0
        if message == "/reset":
            session = agent.new_session()
            seen_returns = 0
            seen_tickets = 0
            print("Started a new chat.\n")
            continue
        if message == "/tickets":
            if not session.tickets:
                print("No tickets in this chat.\n")
            for ticket in session.tickets:
                print(_render_ticket(ticket))
                print()
            continue
        code = turn(message)
        if code:
            return code


def _render_return(record: dict) -> str:
    return "\n".join(
        [
            f"--- return {record['id']} ---",
            f"order: {record['order_id']}",
            f"items: {item_names(record['items'])}",
            f"total: {money(record['item_total'])}",
            f"reason: {record['reason_label']}",
            f"email: {record['email']}",
        ]
    )


def _render_ticket(ticket: dict) -> str:
    lines = [
        f"--- ticket {ticket['id']} | {ticket['priority']} | {ticket['reason_label']} ---",
        f"reason: {ticket['reason_code']}",
        f"summary: {ticket['summary']}",
        f"recommended: {ticket['recommended_action']}",
    ]
    if ticket.get("customer_email"):
        lines.append(f"email: {ticket['customer_email']}")
    if ticket.get("order_id"):
        lines.append(f"order: {ticket['order_id']}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
