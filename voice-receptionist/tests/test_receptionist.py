import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build_config import build_configs
from simulate import agent_text, load_knowledge, load_scenarios, run_scenario, tool_names

CONFIG = ROOT / "config"


def test_every_scenario_follows_the_call_flow():
    knowledge = load_knowledge()
    for scenario in load_scenarios():
        _agent, transcript = run_scenario(scenario, knowledge)
        text = agent_text(transcript).lower()
        names = tool_names(transcript)
        for expected in scenario["expect_tools"]:
            assert expected in names, scenario["id"]
        for forbidden in scenario["forbid_tools"]:
            assert forbidden not in names, scenario["id"]
        for snippet in scenario["expect_text"]:
            assert snippet.lower() in text, (scenario["id"], snippet, text)
        if scenario["expect_tools"]:
            positions = []
            cursor = 0
            for expected in scenario["expect_tools"]:
                cursor = names.index(expected, cursor)
                positions.append(cursor)
                cursor += 1
            assert positions == sorted(positions)


def test_booking_waits_for_a_yes():
    knowledge = load_knowledge()
    scenario = next(item for item in load_scenarios() if item["id"] == "book-drain")
    agent, transcript = run_scenario(scenario, knowledge)
    book = next(turn for turn in transcript if turn.get("name") == "book_appointment")
    assert book["arguments"]["caller_name"] == "Elena Vasquez"
    assert book["arguments"]["service"] == "drain cleaning"
    assert book["arguments"]["day"] == "2026-10-17"
    assert "booked" in agent.summary().lower()
    confirm_at = next(
        index for index, turn in enumerate(transcript) if turn["role"] == "agent" and "lock that in" in turn["text"]
    )
    book_at = next(index for index, turn in enumerate(transcript) if turn.get("name") == "book_appointment")
    assert confirm_at < book_at


def test_configs_embed_the_prompt_and_tools():
    built = build_configs()
    saved = {
        "vapi": json.loads((CONFIG / "vapi-assistant.json").read_text(encoding="utf-8")),
        "retell_llm": json.loads((CONFIG / "retell-llm.json").read_text(encoding="utf-8")),
        "retell_agent": json.loads((CONFIG / "retell-agent.json").read_text(encoding="utf-8")),
    }
    assert saved == built
    prompt = (CONFIG / "system-prompt.md").read_text(encoding="utf-8").strip()
    assert saved["vapi"]["model"]["messages"][0]["content"] == prompt
    assert saved["retell_llm"]["general_prompt"] == prompt
    tool_names_vapi = []
    for tool in saved["vapi"]["model"]["tools"]:
        tool_names_vapi.append(tool.get("function", {}).get("name") or tool.get("name"))
    assert {"check_availability", "book_appointment", "take_message", "transfer_to_human"} <= set(tool_names_vapi)
    assert "+13035550199" in json.dumps(saved["vapi"])
    flow = (ROOT / "docs" / "call-flow.md").read_text(encoding="utf-8")
    assert "```mermaid" in flow
    assert "book_appointment" in flow
