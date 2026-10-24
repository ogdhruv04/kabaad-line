"""Create (or update) the Kabaad Line ElevenLabs agent and its 3 webhook tools from code.

    python -m voice.create_agent --base-url https://kabaad-api.onrender.com            # create
    python -m voice.create_agent --base-url https://kabaad-api.onrender.com --update   # repoint tools / refresh prompt
    python -m voice.create_agent --hindi-voices                                        # list Hindi voices to pick from

Reads ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID and TOOL_SHARED_SECRET from .env. Agent and tool IDs are saved to
voice/agent.json (not secret) so --update can find them. Same result as the manual steps in AGENT_SETUP.md.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

from server import config

API = "https://api.elevenlabs.io"
HERE = Path(__file__).parent
STATE = HERE / "agent.json"
FIRST_MESSAGE = "नमस्ते {{collector_name}} जी! कौन सा डस्टबिन भरा है, या आज कितना कबाड़ उठाया?"


def _http() -> httpx.Client:
    if not config.ELEVENLABS_API_KEY:
        raise SystemExit("Set ELEVENLABS_API_KEY in .env first.")
    return httpx.Client(base_url=API, headers={"xi-api-key": config.ELEVENLABS_API_KEY}, timeout=60)


def _ok(r: httpx.Response) -> dict:
    if r.is_error:
        raise SystemExit(f"{r.request.method} {r.request.url} -> {r.status_code}\n{r.text}")
    return r.json()


def _str(description: str) -> dict:
    return {"type": "string", "description": description}


def _who(var: str = "collector_name") -> dict:  # filled from the session, never guessed by the LLM
    return {"type": "string", "dynamic_variable": var}


def tool_configs(base_url: str) -> dict[str, dict]:
    def webhook(name: str, description: str, properties: dict, required: list[str]) -> dict:
        return {"tool_config": {
            "type": "webhook", "name": name, "description": description, "response_timeout_secs": 20,
            "api_schema": {
                "url": f"{base_url.rstrip('/')}/tools/{name}", "method": "POST",
                "request_headers": {"X-Tool-Secret": config.TOOL_SHARED_SECRET},
                "request_body_schema": {"type": "object", "description": description, "properties": properties, "required": required},
            },
        }}

    return {
        "report_bin_status": webhook(
            "report_bin_status",
            "Log how full a bin is or that it is overflowing. Use whenever the caller mentions a bin, dustbin, kooda or a place that is full.",
            {"location_name": _str("Place the caller mentioned, exactly as they said it (Hindi or English)."),
             "fill_level": _str('Their words for how full: "overflowing", "full", "almost full", "half", "empty", or a percent.'),
             "waste_type": _str("What kind of waste, if mentioned."),
             "note": _str("Anything else they said."),
             "reporter_name": _who()},
            ["location_name", "fill_level"]),
        "log_collection": webhook(
            "log_collection",
            "Log material the collector picked up, with weight in kg.",
            {"material": _str("gatta/cardboard, bottle/PET, plastic, loha/metal, e-waste, kaanch/glass, panni/MLP, organic."),
             "kg": {"type": "number", "description": "Weight in kilograms. Ask if not given."},
             "location_name": _str("Where it was collected, if mentioned."),
             "collector_name": _who()},
            ["material", "kg"]),
        "get_my_route": webhook(
            "get_my_route",
            "Get the caller's planned stops for tomorrow, in order.",
            {"collector_name": _who()},
            []),
    }


def agent_body(tool_ids: list[str]) -> dict:
    tts = {"model_id": "eleven_flash_v2_5"}  # multilingual + low latency; Hindi needs a non-English-only model
    if config.ELEVENLABS_VOICE_ID:
        tts["voice_id"] = config.ELEVENLABS_VOICE_ID
    return {
        "name": "Kabaad Line (Hindi collector line)",
        "tags": ["sociothon-2026", "kabaad-line"],
        "conversation_config": {
            "agent": {
                "first_message": FIRST_MESSAGE,
                "language": "hi",
                "dynamic_variables": {"dynamic_variable_placeholders": {"collector_name": "Ramesh"}},
                "prompt": {"prompt": (HERE / "agent_prompt.md").read_text(), "tool_ids": tool_ids},
            },
            "tts": tts,
        },
    }


def create_or_update(base_url: str, update: bool) -> None:
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    with _http() as h:
        tool_ids = state.get("tool_ids", {})
        for name, body in tool_configs(base_url).items():
            if update and name in tool_ids:
                r = h.patch(f"/v1/convai/tools/{tool_ids[name]}", json=body)
                if r.status_code != 404:
                    _ok(r)
                    print(f"updated tool {name}")
                    continue
            tool_ids[name] = _ok(h.post("/v1/convai/tools", json=body))["id"]
            print(f"created tool {name}: {tool_ids[name]}")
        body = agent_body(list(tool_ids.values()))
        if update and state.get("agent_id"):
            _ok(h.patch(f"/v1/convai/agents/{state['agent_id']}", json=body))
            agent_id = state["agent_id"]
            print(f"updated agent {agent_id}")
        else:
            agent_id = _ok(h.post("/v1/convai/agents/create", json=body))["agent_id"]
            print(f"created agent {agent_id}")
    STATE.write_text(json.dumps({"agent_id": agent_id, "tool_ids": tool_ids, "base_url": base_url}, indent=2) + "\n")
    print(f"\nPut this in web/.env and on Render (kabaad-web):  VITE_ELEVENLABS_AGENT_ID={agent_id}")


def hindi_voices() -> None:
    with _http() as h:
        mine = _ok(h.get("/v2/voices", params={"page_size": 100}))["voices"]
        shared = _ok(h.get("/v1/shared-voices", params={"language": "hi", "page_size": 30, "sort": "usage_character_count_1y"}))["voices"]
    print("In your library:")
    for v in mine:
        print(f"  {v['voice_id']}  {v['name']}  {v.get('labels', {})}")
    print("\nShared Hindi voices (add to library first: POST /v1/voices/add/{public_owner_id}/{voice_id}):")
    for v in shared:
        print(f"  {v['voice_id']}  owner={v['public_owner_id']}  {v['name']}  {v.get('gender')} {v.get('accent')} · {v.get('description', '')[:70]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", help="Public backend URL the webhook tools call, e.g. https://kabaad-api.onrender.com")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--hindi-voices", action="store_true")
    a = ap.parse_args()
    if a.hindi_voices:
        hindi_voices()
    elif a.base_url:
        create_or_update(a.base_url, a.update)
    else:
        ap.error("pass --base-url or --hindi-voices")
