"""Build the importable n8n workflow for the Northline lead-intake demo.

The phrase lists are copied in from classify.py so the in-workflow fallback
matches the local simulator.
"""

from __future__ import annotations

import json
from pathlib import Path

from classify import COLD_PHRASES, HOT_PHRASES, WARM_PHRASES

ROOT = Path(__file__).resolve().parent
PROMPT_PATH = ROOT / "prompts" / "classify.md"
OUT_PATH = ROOT / "workflow" / "lead-intake.n8n.json"


def _node(
    node_id: str,
    name: str,
    node_type: str,
    type_version: float | int,
    x: int,
    y: int,
    parameters: dict,
    *,
    credentials: dict | None = None,
    extra: dict | None = None,
) -> dict:
    node = {
        "parameters": parameters,
        "id": node_id,
        "name": name,
        "type": node_type,
        "typeVersion": type_version,
        "position": [x, y],
    }
    if credentials:
        node["credentials"] = credentials
    if extra:
        node.update(extra)
    return node


def _fallback_js() -> str:
    return f"""const lead = $('Normalize Lead').first().json;
const HOT = {json.dumps(list(HOT_PHRASES))};
const WARM = {json.dumps(list(WARM_PHRASES))};
const COLD = {json.dumps(list(COLD_PHRASES))};
const blob = `${{lead.message || ''}} ${{lead.company || ''}} ${{lead.source || ''}}`.toLowerCase();
const hits = (phrases) => phrases.filter((phrase) => blob.includes(phrase));
let temperature = 'cold';
let reason = 'There is no company and no clear buying signal.';
if (blob.includes('no budget') || blob.includes('just curious') || blob.includes('researching for school')) {{
  temperature = 'cold';
  reason = 'The note shows curiosity or no budget, so it is not a live opportunity.';
}} else if (hits(HOT).length) {{
  temperature = 'hot';
  reason = `The note signals near-term intent (${{hits(HOT)[0]}}).`;
}} else if (hits(WARM).length) {{
  temperature = 'warm';
  reason = `The note asks for information (${{hits(WARM)[0]}}) without a start-now signal.`;
}} else if (hits(COLD).length) {{
  temperature = 'cold';
  reason = `The note is low intent (${{hits(COLD)[0]}}).`;
}} else if (lead.company) {{
  temperature = 'warm';
  reason = 'A company is named, but the note does not say how soon they want to start.';
}}
const who = lead.company ? `${{lead.name || 'Unknown sender'}} at ${{lead.company}}` : (lead.name || 'Unknown sender');
const want = (lead.message || 'did not describe a project').replace(/\\s+/g, ' ').trim();
const shortWant = want.length > 110 ? `${{want.slice(0, 107).trim()}}...` : want;
const nextStep = {{ hot: 'call today', warm: 'send pricing', cold: 'nurture only' }}[temperature];
const summary = `${{who}} wrote: ${{shortWant}}.\\n${{temperature[0].toUpperCase()}}${{temperature.slice(1)}} lead because ${{reason}} Next step: ${{nextStep}}.`;
return [{{ json: {{ ...lead, temperature, summary, reason, classifiedBy: 'rules-fallback' }} }}];
"""


def _parse_js() -> str:
    return """const lead = $('Normalize Lead').first().json;
const body = $input.first().json;
const content = body.choices?.[0]?.message?.content;
if (!content) {
  throw new Error('OpenAI response did not include message content');
}
let parsed;
try {
  parsed = JSON.parse(content);
} catch (error) {
  throw new Error(`OpenAI content was not JSON: ${content.slice(0, 180)}`);
}
const temperature = String(parsed.temperature || '').toLowerCase();
if (!['hot', 'warm', 'cold'].includes(temperature)) {
  throw new Error(`Unexpected temperature: ${temperature}`);
}
const summary = String(parsed.summary || '').trim();
const lines = summary.split(/\\n/).map((line) => line.trim()).filter(Boolean);
if (lines.length !== 2) {
  throw new Error('Summary must be exactly two lines');
}
return [{
  json: {
    ...lead,
    temperature,
    summary: lines.join('\\n'),
    reason: String(parsed.reason || ''),
    classifiedBy: 'openai',
  },
}];
"""


def _compose_js() -> str:
    return r"""const item = $input.first().json;
const first = (item.name || 'there').split(' ')[0];
const bodies = {
  hot: `Hi ${first},\n\nThanks for writing in. A specialist will call you today about the workflow you described.\n\nNorthline Studio`,
  warm: `Hi ${first},\n\nThanks for your interest. Reply with two times that work for a 15-minute call, and we will send a short pricing outline before we meet.\n\nNorthline Studio`,
  cold: `Hi ${first},\n\nThanks for getting in touch. If a workflow project comes up later, reply to this note and we will pick it up from there.\n\nNorthline Studio`,
};
const subjects = {
  hot: 'We got your note and will call today',
  warm: 'Pricing next steps from Northline Studio',
  cold: 'Thanks for contacting Northline Studio',
};
const slackText = [
  `*Hot lead:* ${item.name || 'Unknown'} · ${item.company || 'No company'}`,
  item.email,
  item.phone || 'No phone',
  '',
  item.summary,
  '',
  `Source: ${item.source || 'website-form'}`,
].join('\n');
return [{
  json: {
    ...item,
    emailSubject: subjects[item.temperature] || subjects.warm,
    emailBody: bodies[item.temperature] || bodies.warm,
    slackText,
    sheetTimestamp: new Date().toISOString(),
  },
}];
"""


def _sheet_columns() -> dict:
    fields = [
        ("Timestamp", "={{ $json.sheetTimestamp }}"),
        ("Name", "={{ $json.name }}"),
        ("Email", "={{ $json.email }}"),
        ("Company", "={{ $json.company }}"),
        ("Phone", "={{ $json.phone }}"),
        ("Source", "={{ $json.source }}"),
        ("Temperature", "={{ $json.temperature }}"),
        ("Summary", "={{ $json.summary }}"),
        ("Reason", "={{ $json.reason }}"),
        ("Message", "={{ $json.message }}"),
        ("Classified By", "={{ $json.classifiedBy }}"),
    ]
    schema = [
        {
            "id": name,
            "displayName": name,
            "required": False,
            "defaultMatch": False,
            "display": True,
            "type": "string",
            "canBeUsedToMatch": True,
        }
        for name, _ in fields
    ]
    return {
        "mappingMode": "defineBelow",
        "value": {name: expr for name, expr in fields},
        "matchingColumns": [],
        "schema": schema,
        "attemptToConvertTypes": False,
        "convertFieldsToString": False,
    }


def build_workflow() -> dict:
    prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
    user_payload = (
        "JSON.stringify({ name: $json.name, email: $json.email, company: $json.company, "
        "phone: $json.phone, source: $json.source, message: $json.message })"
    )
    json_body = (
        "={{ JSON.stringify({ model: 'gpt-4o-mini', temperature: 0.2, "
        "response_format: { type: 'json_object' }, messages: ["
        f"{{ role: 'system', content: {json.dumps(prompt)} }}, "
        f"{{ role: 'user', content: {user_payload} }}] }}) }}"
    )
    placeholder = {"id": "REPLACE_ME", "name": "Connect this credential after import"}
    return {
        "name": "Northline Studio — Lead intake",
        "nodes": [
            _node(
                "7c1e9a20-eeee-4a11-8c11-eeeeeeeeeeee",
                "How this flow works",
                "n8n-nodes-base.stickyNote",
                1,
                80,
                40,
                {
                    "content": (
                        "## Northline lead intake\n"
                        "1. Website form posts to this webhook.\n"
                        "2. OpenAI labels the lead hot, warm, or cold and writes a two-line summary.\n"
                        "3. If OpenAI errors, the rules fallback uses the same phrases.\n"
                        "4. Every valid lead is appended to Google Sheets and gets a Gmail reply.\n"
                        "5. Hot leads also post in #hot-leads.\n\n"
                        "Replace every REPLACE_ME credential and the sheet id before activating."
                    ),
                    "height": 260,
                    "width": 420,
                    "color": 5,
                },
            ),
            _node(
                "7c1e9a20-1111-4a11-8c11-111111111111",
                "Form Webhook",
                "n8n-nodes-base.webhook",
                2,
                220,
                400,
                {
                    "httpMethod": "POST",
                    "path": "northline-lead",
                    "responseMode": "responseNode",
                    "options": {},
                },
                extra={"webhookId": "c0ffee00-1111-4a11-8c11-111111111111"},
            ),
            _node(
                "7c1e9a20-2222-4a11-8c11-222222222222",
                "Normalize Lead",
                "n8n-nodes-base.set",
                3.4,
                480,
                400,
                {
                    "assignments": {
                        "assignments": [
                            {"id": "name", "name": "name", "value": "={{ ($json.body?.name || '').replace(/\\s+/g, ' ').trim() }}", "type": "string"},
                            {"id": "email", "name": "email", "value": "={{ ($json.body?.email || '').trim().toLowerCase() }}", "type": "string"},
                            {"id": "company", "name": "company", "value": "={{ ($json.body?.company || '').replace(/\\s+/g, ' ').trim() }}", "type": "string"},
                            {"id": "phone", "name": "phone", "value": "={{ ($json.body?.phone || '').trim() }}", "type": "string"},
                            {"id": "source", "name": "source", "value": "={{ ($json.body?.source || 'website-form').trim() }}", "type": "string"},
                            {"id": "message", "name": "message", "value": "={{ ($json.body?.message || '').replace(/\\s+/g, ' ').trim() }}", "type": "string"},
                        ]
                    },
                    "options": {},
                },
            ),
            _node(
                "7c1e9a20-3333-4a11-8c11-333333333333",
                "Has Email",
                "n8n-nodes-base.if",
                2.2,
                740,
                400,
                {
                    "conditions": {
                        "options": {
                            "caseSensitive": True,
                            "leftValue": "",
                            "typeValidation": "loose",
                        },
                        "conditions": [
                            {
                                "id": "email-present",
                                "leftValue": "={{ $json.email }}",
                                "rightValue": "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$",
                                "operator": {
                                    "type": "string",
                                    "operation": "regex",
                                },
                            }
                        ],
                        "combinator": "and",
                    },
                    "options": {},
                },
            ),
            _node(
                "7c1e9a20-4444-4a11-8c11-444444444444",
                "Respond Invalid",
                "n8n-nodes-base.respondToWebhook",
                1.1,
                1020,
                620,
                {
                    "respondWith": "json",
                    "responseBody": '={{ { "ok": false, "error": "email is required" } }}',
                    "options": {"responseCode": 400},
                },
            ),
            _node(
                "7c1e9a20-5555-4a11-8c11-555555555555",
                "Classify Lead",
                "n8n-nodes-base.httpRequest",
                4.2,
                1020,
                280,
                {
                    "method": "POST",
                    "url": "https://api.openai.com/v1/chat/completions",
                    "authentication": "genericCredentialType",
                    "genericAuthType": "httpHeaderAuth",
                    "sendHeaders": True,
                    "headerParameters": {
                        "parameters": [
                            {"name": "Content-Type", "value": "application/json"}
                        ]
                    },
                    "sendBody": True,
                    "specifyBody": "json",
                    "jsonBody": json_body,
                    "options": {"timeout": 20000},
                },
                credentials={"httpHeaderAuth": {**placeholder, "name": "OpenAI Authorization header"}},
                extra={"onError": "continueErrorOutput"},
            ),
            _node(
                "7c1e9a20-6666-4a11-8c11-666666666666",
                "Parse Classification",
                "n8n-nodes-base.code",
                2,
                1280,
                180,
                {"language": "javaScript", "jsCode": _parse_js()},
            ),
            _node(
                "7c1e9a20-7777-4a11-8c11-777777777777",
                "Rules Fallback",
                "n8n-nodes-base.code",
                2,
                1280,
                400,
                {"language": "javaScript", "jsCode": _fallback_js()},
            ),
            _node(
                "7c1e9a20-8888-4a11-8c11-888888888888",
                "Compose Outreach",
                "n8n-nodes-base.code",
                2,
                1540,
                280,
                {"language": "javaScript", "jsCode": _compose_js()},
            ),
            _node(
                "7c1e9a20-9999-4a11-8c11-999999999999",
                "Append Google Sheet",
                "n8n-nodes-base.googleSheets",
                4.5,
                1800,
                80,
                {
                    "operation": "append",
                    "documentId": {
                        "__rl": True,
                        "mode": "id",
                        "value": "YOUR_GOOGLE_SHEET_ID",
                    },
                    "sheetName": {
                        "__rl": True,
                        "mode": "name",
                        "value": "Leads",
                    },
                    "columns": _sheet_columns(),
                    "options": {},
                },
                credentials={"googleSheetsOAuth2Api": {**placeholder, "name": "Google Sheets account"}},
            ),
            _node(
                "7c1e9a20-aaaa-4a11-8c11-aaaaaaaaaaaa",
                "Is Hot",
                "n8n-nodes-base.if",
                2.2,
                1800,
                300,
                {
                    "conditions": {
                        "options": {
                            "caseSensitive": True,
                            "leftValue": "",
                            "typeValidation": "strict",
                        },
                        "conditions": [
                            {
                                "id": "temp-hot",
                                "leftValue": "={{ $json.temperature }}",
                                "rightValue": "hot",
                                "operator": {"type": "string", "operation": "equals"},
                            }
                        ],
                        "combinator": "and",
                    },
                    "options": {},
                },
            ),
            _node(
                "7c1e9a20-bbbb-4a11-8c11-bbbbbbbbbbbb",
                "Slack Hot Lead",
                "n8n-nodes-base.slack",
                2.2,
                2060,
                200,
                {
                    "resource": "message",
                    "operation": "post",
                    "select": "channel",
                    "channelId": {
                        "__rl": True,
                        "mode": "name",
                        "value": "#hot-leads",
                    },
                    "text": "={{ $json.slackText }}",
                    "otherOptions": {},
                },
                credentials={"slackApi": {**placeholder, "name": "Slack account"}},
            ),
            _node(
                "7c1e9a20-cccc-4a11-8c11-cccccccccccc",
                "Send Gmail Reply",
                "n8n-nodes-base.gmail",
                2.1,
                1800,
                540,
                {
                    "sendTo": "={{ $json.email }}",
                    "subject": "={{ $json.emailSubject }}",
                    "emailType": "text",
                    "message": "={{ $json.emailBody }}",
                    "options": {},
                },
                credentials={"gmailOAuth2": {**placeholder, "name": "Gmail account"}},
            ),
            _node(
                "7c1e9a20-dddd-4a11-8c11-dddddddddddd",
                "Respond OK",
                "n8n-nodes-base.respondToWebhook",
                1.1,
                2060,
                420,
                {
                    "respondWith": "json",
                    "responseBody": '={{ { "ok": true, "temperature": $json.temperature, "summary": $json.summary, "classifiedBy": $json.classifiedBy } }}',
                    "options": {"responseCode": 200},
                },
            ),
        ],
        "connections": {
            "Form Webhook": {
                "main": [[{"node": "Normalize Lead", "type": "main", "index": 0}]]
            },
            "Normalize Lead": {
                "main": [[{"node": "Has Email", "type": "main", "index": 0}]]
            },
            "Has Email": {
                "main": [
                    [{"node": "Classify Lead", "type": "main", "index": 0}],
                    [{"node": "Respond Invalid", "type": "main", "index": 0}],
                ]
            },
            "Classify Lead": {
                "main": [
                    [{"node": "Parse Classification", "type": "main", "index": 0}],
                    [{"node": "Rules Fallback", "type": "main", "index": 0}],
                ]
            },
            "Parse Classification": {
                "main": [[{"node": "Compose Outreach", "type": "main", "index": 0}]]
            },
            "Rules Fallback": {
                "main": [[{"node": "Compose Outreach", "type": "main", "index": 0}]]
            },
            "Compose Outreach": {
                "main": [[
                    {"node": "Append Google Sheet", "type": "main", "index": 0},
                    {"node": "Is Hot", "type": "main", "index": 0},
                    {"node": "Send Gmail Reply", "type": "main", "index": 0},
                    {"node": "Respond OK", "type": "main", "index": 0},
                ]]
            },
            "Is Hot": {
                "main": [
                    [{"node": "Slack Hot Lead", "type": "main", "index": 0}],
                    [],
                ]
            },
        },
        "pinData": {
            "Form Webhook": [
                {
                    "json": {
                        "headers": {"content-type": "application/json"},
                        "body": {
                            "name": "Maya Chen",
                            "email": "maya@brightpath.example",
                            "company": "Brightpath Dental Group",
                            "phone": "303-555-0164",
                            "source": "website-form",
                            "message": "We need the missed-call text-back live this week. Budget is approved and I am the decision maker. Please call me today.",
                        },
                    }
                }
            ]
        },
        "settings": {"executionOrder": "v1"},
        "staticData": None,
        "meta": {
            "templateCredsSetupCompleted": False,
            "instanceId": "northline-portfolio-demo",
        },
        "versionId": "7c1e9a20-0000-4a11-8c11-000000000001",
        "active": False,
        "tags": [],
    }


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(build_workflow(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
