"""Write the Vapi assistant and Retell LLM configs from the shared prompt and tools."""

from __future__ import annotations

import json
from pathlib import Path

from tools import TOOL_SCHEMAS

ROOT = Path(__file__).resolve().parent
PROMPT_PATH = ROOT / "config" / "system-prompt.md"
KNOWLEDGE_PATH = ROOT / "config" / "knowledge.json"
VAPI_PATH = ROOT / "config" / "vapi-assistant.json"
RETELL_LLM_PATH = ROOT / "config" / "retell-llm.json"
RETELL_AGENT_PATH = ROOT / "config" / "retell-agent.json"


def _openai_tool(schema: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": schema["name"],
            "description": schema["description"],
            "parameters": schema["parameters"],
        },
    }


def build_configs() -> dict[str, dict]:
    prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
    knowledge = json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    function_tools = [_openai_tool(schema) for schema in TOOL_SCHEMAS if schema["name"] != "transfer_to_human"]
    transfer = {
        "type": "transferCall",
        "function": {
            "name": "transfer_to_human",
            "description": "Transfer the caller to the Peak Plumbing dispatcher.",
            "parameters": TOOL_SCHEMAS[-1]["parameters"],
        },
        "destinations": [
            {
                "type": "number",
                "number": knowledge["transfer_number"],
                "description": "Peak Plumbing dispatcher",
            }
        ],
    }
    vapi = {
        "name": "Peak Plumbing Denver Receptionist",
        "firstMessage": (
            "Thanks for calling Peak Plumbing Denver. "
            "This is the virtual receptionist. How can I help you today?"
        ),
        "model": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.4,
            "messages": [{"role": "system", "content": prompt}],
            "tools": function_tools + [transfer],
        },
        "voice": {
            "provider": "11labs",
            "voiceId": "EXAVITQu4vr4xnSDxMaL",
            "stability": 0.5,
            "similarityBoost": 0.75,
        },
        "endCallFunctionEnabled": True,
        "recordingEnabled": True,
        "silenceTimeoutSeconds": 20,
        "maxDurationSeconds": 600,
        "backgroundSound": "office",
        "serverUrl": "https://YOUR_N8N.example/webhook/peak-call-summary",
        "analysisPlan": {
            "summaryPrompt": "Summarize the caller, the request, and the outcome in 4 lines.",
        },
    }
    retell_tools = []
    for schema in TOOL_SCHEMAS:
        if schema["name"] == "transfer_to_human":
            retell_tools.append(
                {
                    "type": "transfer_call",
                    "name": "transfer_to_human",
                    "description": schema["description"],
                    "transfer_destination": {
                        "type": "predefined",
                        "number": knowledge["transfer_number"],
                    },
                    "transfer_option": {"type": "cold_transfer"},
                }
            )
            continue
        retell_tools.append(
            {
                "type": "custom",
                "name": schema["name"],
                "description": schema["description"],
                "url": f"https://YOUR_SERVER.example/tools/{schema['name'].replace('_', '-')}",
                "speak_during_execution": True,
                "speak_after_execution": True,
                "parameters": schema["parameters"],
            }
        )
    retell_llm = {
        "model": "gpt-4o-mini",
        "general_prompt": prompt,
        "general_tools": retell_tools,
        "starting_state": "greeting",
    }
    retell_agent = {
        "agent_name": "Peak Plumbing Denver Receptionist",
        "voice_id": "11labs-Rachel",
        "language": "en-US",
        "response_engine": {"type": "retell-llm", "llm_id": "REPLACE_AFTER_CREATING_LLM"},
        "webhook_url": "https://YOUR_N8N.example/webhook/peak-call-summary",
    }
    return {"vapi": vapi, "retell_llm": retell_llm, "retell_agent": retell_agent}


def main() -> None:
    configs = build_configs()
    VAPI_PATH.write_text(json.dumps(configs["vapi"], indent=2) + "\n", encoding="utf-8")
    RETELL_LLM_PATH.write_text(json.dumps(configs["retell_llm"], indent=2) + "\n", encoding="utf-8")
    RETELL_AGENT_PATH.write_text(json.dumps(configs["retell_agent"], indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {VAPI_PATH}")


if __name__ == "__main__":
    main()
