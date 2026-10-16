"""Run the Northline lead-intake sample without n8n.

Writes a sheet CSV, Slack messages for hot leads, Gmail replies, and an HTML
proof page. With OPENAI_API_KEY set, classification can call the same prompt
the workflow uses. The default path is the offline rules engine.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from classify import Classification, email_copy, normalize_lead, slack_text, valid_email
from classify import classify as classify_rules

ROOT = Path(__file__).resolve().parent
PAYLOAD_DIR = ROOT / "sample-payloads"
SAMPLE_DIR = ROOT / "samples"
PROMPT_PATH = ROOT / "prompts" / "classify.md"

SHEET_FIELDS = [
    "timestamp",
    "name",
    "email",
    "company",
    "phone",
    "source",
    "temperature",
    "summary",
    "reason",
    "message",
    "classified_by",
]


def classify_with_openai(lead) -> Classification:
    prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
    payload = {
        "model": "gpt-4o-mini",
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "name": lead.name,
                        "email": lead.email,
                        "company": lead.company,
                        "phone": lead.phone,
                        "source": lead.source,
                        "message": lead.message,
                    }
                ),
            },
        ],
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read().decode())
    parsed = json.loads(body["choices"][0]["message"]["content"])
    temperature = str(parsed["temperature"]).lower()
    if temperature not in {"hot", "warm", "cold"}:
        raise ValueError(f"Unexpected temperature: {temperature}")
    summary = str(parsed["summary"]).strip()
    lines = [line.strip() for line in summary.splitlines() if line.strip()]
    if len(lines) != 2:
        raise ValueError("Summary must be exactly two lines")
    return Classification(temperature=temperature, summary="\n".join(lines), reason=str(parsed.get("reason") or ""))


def process_payload(raw: dict, *, use_openai: bool, timestamp: str) -> dict:
    lead = normalize_lead(raw)
    if not valid_email(lead.email):
        return {
            "ok": False,
            "error": "email is required",
            "lead": lead,
            "timestamp": timestamp,
        }
    if use_openai and os.environ.get("OPENAI_API_KEY"):
        result = classify_with_openai(lead)
        classified_by = "openai"
    else:
        result = classify_rules(lead)
        classified_by = "rules"
    subject, body = email_copy(lead, result)
    row = {
        "timestamp": timestamp,
        "name": lead.name,
        "email": lead.email,
        "company": lead.company,
        "phone": lead.phone,
        "source": lead.source,
        "temperature": result.temperature,
        "summary": result.summary,
        "reason": result.reason,
        "message": lead.message,
        "classified_by": classified_by,
    }
    return {
        "ok": True,
        "lead": lead,
        "result": result,
        "classified_by": classified_by,
        "email_subject": subject,
        "email_body": body,
        "slack_text": slack_text(lead, result) if result.temperature == "hot" else "",
        "row": row,
        "timestamp": timestamp,
    }


def load_payloads() -> list[tuple[str, dict]]:
    files = sorted(PAYLOAD_DIR.glob("*.json"))
    return [(path.stem, json.loads(path.read_text(encoding="utf-8"))) for path in files]


def render_report(runs: list[tuple[str, dict]]) -> str:
    cards = []
    sheet_rows = []
    extras = []
    for name, run in runs:
        if not run["ok"]:
            cards.append(
                f"<article class='card cold'><p class='kicker'>{name}</p>"
                f"<h2>Rejected</h2><p>{run['error']}</p></article>"
            )
            continue
        temp = run["result"].temperature
        summary = "<br>".join(run["result"].summary.split("\n"))
        cards.append(
            f"<article class='card {temp}'><p class='kicker'>{name} · {run['classified_by']}</p>"
            f"<h2>{run['lead'].name}</h2><p class='temp'>{temp}</p><p>{summary}</p></article>"
        )
        sheet_rows.append(run["row"])
        if run["slack_text"]:
            extras.append(
                "<section><h3>Slack · #hot-leads</h3>"
                f"<pre>{_escape(run['slack_text'])}</pre></section>"
            )
        extras.append(
            f"<section><h3>Gmail · { _escape(run['email_subject']) }</h3>"
            f"<p class='to'>To { _escape(run['lead'].email) }</p>"
            f"<pre>{_escape(run['email_body'])}</pre></section>"
        )
    header = "".join(f"<th>{field}</th>" for field in SHEET_FIELDS if field != "message")
    body = []
    for row in sheet_rows:
        cells = "".join(
            f"<td>{_escape(row[field]).replace(chr(10), '<br>')}</td>"
            for field in SHEET_FIELDS
            if field != "message"
        )
        body.append(f"<tr class='{row['temperature']}'>{cells}</tr>")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Northline lead intake — sample run</title>
  <style>
    :root {{ color-scheme: light; }}
    body {{ margin: 0; font-family: "Iowan Old Style", Palatino, Georgia, serif; background: #f3efe6; color: #1d1a16; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 24px 64px; }}
    h1 {{ font-weight: 500; font-size: 40px; margin: 0 0 8px; }}
    .lede {{ max-width: 640px; font-family: "Avenir Next", "Segoe UI", sans-serif; color: #4d463c; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin: 28px 0; }}
    .card {{ background: white; border-radius: 16px; padding: 16px 18px; box-shadow: 0 1px 0 rgba(0,0,0,.04); }}
    .card h2 {{ margin: 0; font-size: 22px; font-weight: 500; }}
    .kicker {{ font-family: "Avenir Next", "Segoe UI", sans-serif; font-size: 12px; letter-spacing: .08em; text-transform: uppercase; color: #6d6458; margin: 0 0 8px; }}
    .temp {{ display: inline-block; margin: 8px 0; padding: 2px 8px; border-radius: 999px; font-family: "Avenir Next", "Segoe UI", sans-serif; font-size: 12px; text-transform: uppercase; letter-spacing: .06em; }}
    .hot .temp {{ background: #f3d2c4; }}
    .warm .temp {{ background: #f3e3b8; }}
    .cold .temp {{ background: #d9e2ea; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 16px; overflow: hidden; font-family: "Avenir Next", "Segoe UI", sans-serif; font-size: 13px; }}
    th, td {{ text-align: left; padding: 10px 12px; vertical-align: top; border-bottom: 1px solid #eee7db; }}
    th {{ font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: #6d6458; }}
    tr.hot td:first-child {{ box-shadow: inset 3px 0 0 #c45c26; }}
    .split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 28px; }}
    section {{ background: white; border-radius: 16px; padding: 16px 18px; }}
    pre {{ white-space: pre-wrap; font-family: "Avenir Next", "Segoe UI", sans-serif; font-size: 14px; line-height: 1.45; }}
    .to {{ color: #6d6458; font-family: "Avenir Next", "Segoe UI", sans-serif; }}
    @media (max-width: 800px) {{ .split {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <main>
    <p class="kicker">Gig 1 sample run</p>
    <h1>Northline lead intake</h1>
    <p class="lede">Offline run of the same rules the n8n workflow uses when OpenAI is unavailable. Hot leads get a Slack alert. Every valid lead gets a sheet row and a Gmail reply.</p>
    <div class="grid">{''.join(cards)}</div>
    <h2>Google Sheet · Leads</h2>
    <table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>
    <div class="split">{''.join(extras)}</div>
  </main>
</body>
</html>
"""


def _escape(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def write_samples(runs: list[tuple[str, dict]]) -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    slack_dir = SAMPLE_DIR / "slack"
    email_dir = SAMPLE_DIR / "emails"
    slack_dir.mkdir(exist_ok=True)
    email_dir.mkdir(exist_ok=True)
    for path in list(slack_dir.glob("*.txt")) + list(email_dir.glob("*.txt")):
        path.unlink()

    rows = []
    export = []
    for name, run in runs:
        export.append(
            {
                "payload": name,
                "ok": run["ok"],
                "error": run.get("error"),
                "temperature": run["result"].temperature if run["ok"] else None,
                "summary": run["result"].summary if run["ok"] else None,
                "reason": run["result"].reason if run["ok"] else None,
                "classified_by": run.get("classified_by"),
                "slack": bool(run.get("slack_text")),
            }
        )
        if not run["ok"]:
            continue
        rows.append(run["row"])
        (email_dir / f"{name}.txt").write_text(
            f"To: {run['lead'].email}\nSubject: {run['email_subject']}\n\n{run['email_body']}\n",
            encoding="utf-8",
        )
        if run["slack_text"]:
            (slack_dir / f"{name}.txt").write_text(run["slack_text"] + "\n", encoding="utf-8")

    with (SAMPLE_DIR / "leads.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SHEET_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (SAMPLE_DIR / "run.json").write_text(json.dumps(export, indent=2) + "\n", encoding="utf-8")
    (SAMPLE_DIR / "run-report.html").write_text(render_report(runs), encoding="utf-8")


def run_samples(*, use_openai: bool) -> list[tuple[str, dict]]:
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    runs = [
        (name, process_payload(payload, use_openai=use_openai, timestamp=stamp))
        for name, payload in load_payloads()
    ]
    write_samples(runs)
    return runs


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate the Northline n8n lead intake.")
    parser.add_argument("--openai", action="store_true", help="Use OPENAI_API_KEY when it is set.")
    args = parser.parse_args()
    runs = run_samples(use_openai=args.openai)
    ok = [run for _, run in runs if run["ok"]]
    rejected = len(runs) - len(ok)
    hot = sum(1 for run in ok if run["result"].temperature == "hot")
    print(f"Processed {len(runs)} payloads: {len(ok)} accepted, {rejected} rejected, {hot} Slack alerts.")
    print(f"Wrote {SAMPLE_DIR / 'run-report.html'}")


if __name__ == "__main__":
    main()
