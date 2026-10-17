"""Run the bundled cases through the mock agent and print resolution vs escalation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from support_agent.agent import SupportAgent

CASES_PATH = Path(__file__).resolve().parent / "eval_cases.json"


@dataclass
class CaseResult:
    id: str
    outcome: str
    expected: str
    ok: bool
    detail: str = ""
    reply: str = ""


@dataclass
class EvalReport:
    mode: str
    as_of: str
    results: list[CaseResult] = field(default_factory=list)
    returns_created: int = 0
    tickets_opened: int = 0
    high_priority_tickets: int = 0

    @property
    def cases(self) -> int:
        return len(self.results)

    @property
    def resolved(self) -> int:
        return sum(1 for result in self.results if result.outcome == "resolved")

    @property
    def escalated(self) -> int:
        return sum(1 for result in self.results if result.outcome == "escalated")

    @property
    def label_matches(self) -> int:
        return sum(1 for result in self.results if result.ok)

    @property
    def failures(self) -> list[CaseResult]:
        return [result for result in self.results if not result.ok]


def load_cases(path: Path | None = None) -> list[dict]:
    raw = json.loads((path or CASES_PATH).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("Eval cases must be a non-empty list.")
    return raw


def run_eval(cases: list[dict] | None = None) -> EvalReport:
    agent = SupportAgent.create(mode="mock")
    report = EvalReport(mode="mock", as_of=agent.catalog.as_of.isoformat())
    for case in cases or load_cases():
        result, returns_created, tickets, high = _run_case(agent, case)
        report.results.append(result)
        report.returns_created += returns_created
        report.tickets_opened += tickets
        report.high_priority_tickets += high
    return report


def format_report(report: EvalReport) -> str:
    width = max(len("id"), *(len(result.id) for result in report.results))
    lines = [
        "Northline support eval",
        f"mode: {report.mode}",
        f"as_of: {report.as_of}",
        f"cases: {report.cases}",
        f"resolved: {report.resolved}",
        f"escalated: {report.escalated}",
        f"resolution_rate: {_percent(report.resolved, report.cases)}",
        f"escalation_rate: {_percent(report.escalated, report.cases)}",
        f"label_matches: {report.label_matches}",
        f"label_accuracy: {_percent(report.label_matches, report.cases)}",
        f"returns_created: {report.returns_created}",
        f"tickets_opened: {report.tickets_opened}",
        f"high_priority_tickets: {report.high_priority_tickets}",
        "",
        f"{'id'.ljust(width)}  outcome    expected   ok",
    ]
    for result in report.results:
        ok = "yes" if result.ok else "no"
        lines.append(
            f"{result.id.ljust(width)}  {result.outcome.ljust(10)} {result.expected.ljust(10)} {ok}"
        )
    if report.failures:
        lines.append("")
        lines.append("failures:")
        for result in report.failures:
            lines.append(f"- {result.id}: {result.detail}")
            if result.reply:
                lines.append(result.reply)
    return "\n".join(lines)


def main() -> int:
    report = run_eval()
    print(format_report(report))
    return 0 if report.label_matches == report.cases else 1


def _run_case(agent: SupportAgent, case: dict) -> tuple[CaseResult, int, int, int]:
    session = agent.new_session()
    replies: list[str] = []
    for turn in case["turns"]:
        result = agent.handle(session, turn)
        replies.append(result.reply)
    outcome = "escalated" if session.tickets else "resolved"
    blob = "\n".join(replies)
    staff = json.dumps(session.tickets)
    problems: list[str] = []
    if outcome != case["expect"]:
        problems.append(f"outcome {outcome} != {case['expect']}")
    if "expect_return" in case:
        opened = len(session.returns) > 0
        if opened != bool(case["expect_return"]):
            problems.append(f"return opened={opened}")
    if case.get("expect_reason"):
        reasons = [ticket["reason_code"] for ticket in session.tickets]
        if case["expect_reason"] not in reasons:
            problems.append(f"reasons {reasons}")
    if case.get("expect_priority"):
        priorities = [ticket["priority"] for ticket in session.tickets]
        if case["expect_priority"] not in priorities:
            problems.append(f"priorities {priorities}")
    for needle in case.get("contains", []):
        if needle not in blob and needle not in staff:
            problems.append(f"missing {needle!r}")
    for needle in case.get("absent", []):
        if needle in blob or needle in staff:
            problems.append(f"leaked {needle!r}")
    case_result = CaseResult(
        id=case["id"],
        outcome=outcome,
        expected=case["expect"],
        ok=not problems,
        detail="; ".join(problems),
        reply=blob if problems else "",
    )
    high = sum(1 for ticket in session.tickets if ticket["priority"] == "high")
    return case_result, len(session.returns), len(session.tickets), high


def _percent(part: int, whole: int) -> str:
    if whole == 0:
        return "0.0%"
    return f"{(100 * part / whole):.1f}%"


if __name__ == "__main__":
    raise SystemExit(main())
