# Northline Studio lead intake

A website form becomes a hot, warm, or cold lead, a two-line summary, a Google Sheet row, a Gmail reply, and a Slack alert when the lead is hot.

## What is in this folder

- `workflow/lead-intake.n8n.json` — import this into n8n
- `prompts/classify.md` — the instruction the OpenAI step uses
- `simulate.py` — the same rules, run locally with no n8n and no API key
- `sample-payloads/` — five form posts, including a missing email and a messy hot lead
- `samples/` — the last sample run

## Sample run

```bash
python3 -m pip install -r requirements.txt
python3 simulate.py
python3 -m pytest -q tests
```

Open `samples/run-report.html`. Hot leads are Maya Chen and Jorge Alvarez. Sam Student is cold and does not post to Slack. The payload with no email is rejected.

Set `OPENAI_API_KEY` and run `python3 simulate.py --openai` to classify with the same prompt the workflow sends. Without the key, the script uses `classify.py`.

Regenerate the workflow after editing the prompt or the phrase lists:

```bash
python3 build_workflow.py
```

## Import into n8n

1. In n8n, choose Import from File and select `workflow/lead-intake.n8n.json`.
2. Create a Header Auth credential named for OpenAI. Header `Authorization`, value `Bearer YOUR_KEY`. Attach it to **Classify Lead**.
3. Connect Google Sheets, Slack, and Gmail on the three action nodes. Replace `YOUR_GOOGLE_SHEET_ID`. The sheet tab must be named `Leads` and the columns must match the node (Timestamp, Name, Email, Company, Phone, Source, Temperature, Summary, Reason, Message, Classified By).
4. Activate the workflow and POST to `/webhook/northline-lead`.

```bash
curl -X POST "$N8N_URL/webhook/northline-lead" \
  -H 'content-type: application/json' \
  -d @sample-payloads/hot-lead.json
```

The webhook answers with `{ "ok": true, "temperature": "hot", "summary": "..." }`. If OpenAI fails, **Rules Fallback** uses the same phrases as the local simulator and the flow still writes the sheet.

Do not activate the workflow until the `REPLACE_ME` credentials are connected. The file ships inactive on purpose.
