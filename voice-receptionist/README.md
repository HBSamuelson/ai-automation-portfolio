# Peak Plumbing Denver receptionist

Config for an inbound voice receptionist on Vapi or Retell, plus a text simulator that walks the same call flow without placing a phone call.

## Files

- `config/system-prompt.md` — what the agent is allowed to say
- `config/knowledge.json` — hours, service area, price ranges, transfer number
- `config/vapi-assistant.json` — assistant payload, including tools
- `config/retell-llm.json` and `config/retell-agent.json` — the same prompt and tools in Retell's shape
- `docs/call-flow.md` — mermaid diagram
- `scenarios/` — scripted callers
- `samples/call-report.html` — one booked call

The transfer number `+1 303 555 0199` and the shop line `(303) 555-0190` are fictional.

## Run the simulator

```bash
python3 -m pip install -r requirements.txt
python3 simulate.py
python3 simulate.py --scenario book-drain
python3 -m pytest -q tests
```

`python3 build_config.py` rewrites the Vapi and Retell JSON from the prompt and tool schemas so they cannot drift.

## Tools

| Tool | When the agent calls it |
| --- | --- |
| `check_availability` | Before offering a morning or afternoon window |
| `book_appointment` | Only after the caller says yes |
| `take_message` | After-hours emergency, once it has a name and phone |
| `transfer_to_human` | The caller asks for a person, or agrees after a second unclear reply |

Friday morning on 2026-10-16 is already booked in the demo calendar, so the busy-window scenario has to pick another time.

## Put it on an account

Vapi: create an assistant from `config/vapi-assistant.json`. Point `serverUrl` at the n8n webhook that should store the call summary. The voice id is an ElevenLabs voice id you can swap.

Retell: create an LLM from `config/retell-llm.json`, then an agent from `config/retell-agent.json`, and replace `REPLACE_AFTER_CREATING_LLM` with that LLM id. Custom tool URLs are placeholders until a server implements them. The text simulator is the stand-in for those endpoints.
