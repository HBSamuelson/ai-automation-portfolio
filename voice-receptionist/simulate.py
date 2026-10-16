"""Run scripted calls through the Peak Plumbing receptionist."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from receptionist import Receptionist
from tools import Calendar

ROOT = Path(__file__).resolve().parent
SCENARIO_DIR = ROOT / "scenarios"
SAMPLE_DIR = ROOT / "samples"
KNOWLEDGE_PATH = ROOT / "config" / "knowledge.json"


def load_knowledge() -> dict:
    return json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))


def load_scenarios() -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(SCENARIO_DIR.glob("*.json"))
    ]


def run_scenario(scenario: dict, knowledge: dict) -> tuple[Receptionist, list[dict]]:
    now = datetime.fromisoformat(scenario["now"])
    busy = {tuple(pair) for pair in scenario.get("busy", [["2026-10-16", "morning"]])}
    calendar = Calendar(busy=busy)
    agent = Receptionist(knowledge, calendar, now)
    transcript = [{"role": "agent", "text": agent.greet()}]
    for line in scenario["lines"]:
        transcript.append({"role": "caller", "text": line})
        for event in agent.handle(line):
            if event["type"] == "agent":
                transcript.append({"role": "agent", "text": event["text"]})
            else:
                transcript.append(
                    {
                        "role": "tool",
                        "name": event["name"],
                        "arguments": event["arguments"],
                        "result": event["result"],
                    }
                )
    return agent, transcript


def agent_text(transcript: list[dict]) -> str:
    return "\n".join(turn["text"] for turn in transcript if turn["role"] == "agent")


def tool_names(transcript: list[dict]) -> list[str]:
    return [turn["name"] for turn in transcript if turn["role"] == "tool"]


def render_transcript(scenario: dict, transcript: list[dict], summary: str) -> str:
    blocks = []
    for turn in transcript:
        if turn["role"] == "tool":
            blocks.append(
                f"<p class='tool'><b>{turn['name']}</b> {json.dumps(turn['arguments'])}</p>"
            )
        else:
            who = "Peak" if turn["role"] == "agent" else "Caller"
            blocks.append(f"<p class='{turn['role']}'><b>{who}.</b> { _esc(turn['text']) }</p>")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Peak Plumbing — { _esc(scenario['id']) }</title>
  <style>
    body {{ margin: 0; background: #f4f0e6; color: #1c1914; font-family: Georgia, serif; }}
    main {{ max-width: 760px; margin: 0 auto; padding: 36px 20px 72px; }}
    h1 {{ font-weight: 500; font-size: 36px; margin-bottom: 0; }}
    .meta {{ font-family: "Avenir Next", "Segoe UI", sans-serif; color: #5c564c; }}
    .log {{ background: white; border-radius: 18px; padding: 8px 18px; margin-top: 20px; }}
    p {{ line-height: 1.45; }}
    .caller b {{ color: #8a4b12; }}
    .tool {{ font-family: "Avenir Next", "Segoe UI", sans-serif; font-size: 13px; background: #efe7c8; border-radius: 10px; padding: 8px 10px; }}
    pre {{ white-space: pre-wrap; font-family: "Avenir Next", "Segoe UI", sans-serif; background: #1c1914; color: #f4f0e6; padding: 16px; border-radius: 16px; }}
    .flow {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0; font-family: "Avenir Next", "Segoe UI", sans-serif; font-size: 13px; }}
    .flow span {{ background: white; border-radius: 999px; padding: 6px 10px; }}
  </style>
</head>
<body>
  <main>
    <p class="meta">Gig 4 sample call · { _esc(scenario['id']) }</p>
    <h1>Peak Plumbing Denver</h1>
    <div class="flow">
      <span>Greeting</span><span>Intent</span><span>Availability</span><span>Confirm</span><span>Book or transfer</span><span>Summary</span>
    </div>
    <div class="log">{''.join(blocks)}</div>
    <h2>Call summary</h2>
    <pre>{_esc(summary)}</pre>
  </main>
</body>
</html>
"""


def _esc(value: str) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_sample(scenario: dict, transcript: list[dict], summary: str) -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    stem = scenario["id"]
    lines = []
    for turn in transcript:
        if turn["role"] == "tool":
            lines.append(f"[tool] {turn['name']} {json.dumps(turn['arguments'])}")
        else:
            lines.append(f"{turn['role']}: {turn['text']}")
    (SAMPLE_DIR / f"{stem}.txt").write_text("\n".join(lines) + f"\n\n{summary}\n", encoding="utf-8")
    if scenario["id"] == "book-drain":
        (SAMPLE_DIR / "call-report.html").write_text(
            render_transcript(scenario, transcript, summary),
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate Peak Plumbing receptionist calls.")
    parser.add_argument("--scenario", help="Run one scenario id. Default runs every file in scenarios/.")
    args = parser.parse_args()
    knowledge = load_knowledge()
    scenarios = load_scenarios()
    if args.scenario:
        scenarios = [scenario for scenario in scenarios if scenario["id"] == args.scenario]
        if not scenarios:
            raise SystemExit(f"No scenario named {args.scenario}")
    for scenario in scenarios:
        agent, transcript = run_scenario(scenario, knowledge)
        summary = agent.summary()
        write_sample(scenario, transcript, summary)
        print(f"{scenario['id']}: {summary.splitlines()[2]}")
    print(f"Wrote transcripts to {SAMPLE_DIR}")


if __name__ == "__main__":
    main()
