# Northline support agent

A customer-support agent for **Northline Supply**, a fictional outdoor shop. It answers from a fixed FAQ, looks up an order only when the email matches, opens a standard return, and writes a ticket when a person should decide.

Northline is invented. Orders, emails, and policy lines in this folder are mock data. No API key is required for the tests or the eval.

## The problem

A support bot that answers from memory will invent a tracking number or approve a refund the desk is not allowed to make. The costly misses are a leaked order, a return outside the window, and a customer who asked for a person and got another paragraph.

## How it works

The CLI and the web desk share one tool loop. A planner chooses the next tool, or the reply. With `OPENAI_API_KEY` unset, the planner is an offline policy. With a key, the same tools go to an OpenAI-compatible chat API (`OPENAI_BASE_URL` and `OPENAI_MODEL` optional; the model default is `gpt-4o-mini`).

The tools enforce the rule:

- `search_faq` returns a bundled answer. No match becomes a ticket. The agent does not guess.
- `lookup_order` needs the order id and the email on the order. A mismatch returns no items, address, or status.
- `check_return_eligibility` and `create_return` open an RMA only when the order was delivered, is inside 30 days, is not final sale, and was not worn or washed.
- `escalate_to_human` writes the staff ticket. The summary is filled from the order the email unlocked, not from the model's prose.

Damage, cancellations, price matches, chargebacks, and an explicit request for a person are tickets. The desk date is fixed at 7 October 2026 so the 30-day window does not drift.

## Run

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest -q
python3 -m support_agent.eval
python3 -m support_agent.cli --mock
python3 -m support_agent.webapp --mock
```

The desk listens on [http://127.0.0.1:8741](http://127.0.0.1:8741). Copy `.env.example` if you want live mode. Leave `OPENAI_API_KEY` empty to stay on the mock.

Sample orders are in `support_agent/data/orders.json`. `ORD-1042` / `ava.chen@northline.example` is in transit. `ORD-0988` / `mina.park@northline.example` is outside the return window.

## Eval

`python3 -m support_agent.eval` runs the bundled cases through the mock planner. Resolved means the chat ended with no ticket. Escalated means a ticket was opened. Label accuracy is whether that outcome, the expected reason and priority, and the reply checks matched `support_agent/eval_cases.json`.

This is the measured summary:

```text
mode: mock
as_of: 2026-10-07
cases: 22
resolved: 14
escalated: 8
resolution_rate: 63.6%
escalation_rate: 36.4%
label_matches: 22
label_accuracy: 100.0%
returns_created: 2
tickets_opened: 8
high_priority_tickets: 2
```

14 resolved of 22, and 22 of 22 labeled correctly. The same command prints the case list. These numbers measure the mock policy and the tools, not a live model.
