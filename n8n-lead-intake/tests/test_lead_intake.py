import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build_workflow import build_workflow
from classify import classify, normalize_lead
from simulate import process_payload

WORKFLOW_PATH = ROOT / "workflow" / "lead-intake.n8n.json"


def _payload(name: str) -> dict:
    return json.loads((ROOT / "sample-payloads" / name).read_text(encoding="utf-8"))


def test_sample_temperatures():
    expected = {
        "hot-lead.json": "hot",
        "warm-lead.json": "warm",
        "cold-lead.json": "cold",
        "messy-hot-lead.json": "hot",
    }
    for filename, temperature in expected.items():
        result = classify(normalize_lead(_payload(filename)))
        assert result.temperature == temperature
        assert len(result.summary_lines()) == 2


def test_messy_lead_is_normalized():
    lead = normalize_lead(_payload("messy-hot-lead.json"))
    assert lead.name == "Jorge Alvarez"
    assert lead.email == "jorge@alvarezhvac.example"


def test_missing_email_is_rejected_and_hot_leads_alert_slack():
    rejected = process_payload(_payload("missing-email.json"), use_openai=False, timestamp="2026-10-15T12:00:00+00:00")
    assert rejected["ok"] is False
    hot = process_payload(_payload("hot-lead.json"), use_openai=False, timestamp="2026-10-15T12:00:00+00:00")
    warm = process_payload(_payload("warm-lead.json"), use_openai=False, timestamp="2026-10-15T12:00:00+00:00")
    assert hot["slack_text"]
    assert "Maya Chen" in hot["slack_text"]
    assert warm["slack_text"] == ""
    assert "call you today" in hot["email_body"]
    assert hot["row"]["temperature"] == "hot"


def test_workflow_file_matches_builder_and_reaches_every_channel():
    built = build_workflow()
    saved = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert saved == built
    names = {node["name"] for node in saved["nodes"]}
    assert {
        "Form Webhook",
        "Classify Lead",
        "Rules Fallback",
        "Append Google Sheet",
        "Slack Hot Lead",
        "Send Gmail Reply",
    } <= names
    for source, bundle in saved["connections"].items():
        assert source in names
        for output in bundle["main"]:
            for link in output:
                assert link["node"] in names
    classify_node = next(node for node in saved["nodes"] if node["name"] == "Classify Lead")
    assert classify_node["parameters"]["url"] == "https://api.openai.com/v1/chat/completions"
    assert classify_node["onError"] == "continueErrorOutput"
    fallback = next(node for node in saved["nodes"] if node["name"] == "Rules Fallback")
    assert "budget is approved" in fallback["parameters"]["jsCode"]
    assert "REPLACE_ME" in json.dumps(saved)
    assert saved["active"] is False
    webhook = next(node for node in saved["nodes"] if node["name"] == "Form Webhook")
    assert webhook["parameters"]["path"] == "northline-lead"
