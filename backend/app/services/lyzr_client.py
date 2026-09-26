"""
Wrapper around the Lyzr Agent API. Currently supports the Protocol
Criteria Agent; add more agent_id constants here as Phase 3/4 agents
get deployed in Lyzr Studio.
"""

import os
import json
import requests
from typing import Any

LYZR_API_KEY = os.environ.get("LYZR_API_KEY")
LYZR_USER_ID = os.environ.get("LYZR_USER_ID", "ajanshul02@gmail.com")
LYZR_INFERENCE_URL = os.environ.get(
    "LYZR_INFERENCE_URL", "https://agent-prod.studio.lyzr.ai/v3/inference/chat/"
)

PROTOCOL_CRITERIA_AGENT_ID = os.environ.get(
    "LYZR_PROTOCOL_CRITERIA_AGENT_ID", "6ab108f7c9090433f7a1b4bb"
)


class LyzrAgentError(Exception):
    pass


def _call_agent(agent_id: str, session_id: str, message: str) -> str:
    if not LYZR_API_KEY:
        raise LyzrAgentError("LYZR_API_KEY not set in environment")

    response = requests.post(
        LYZR_INFERENCE_URL,
        headers={"Content-Type": "application/json", "x-api-key": LYZR_API_KEY},
        json={
            "user_id": LYZR_USER_ID,
            "agent_id": agent_id,
            "session_id": session_id,
            "message": message,
        },
        timeout=60,
    )

    if response.status_code != 200:
        raise LyzrAgentError(f"Lyzr agent call failed ({response.status_code}): {response.text}")

    data = response.json()
    return data.get("response", "")


def extract_protocol_criteria(protocol_text: str, protocol_id: str) -> dict[str, Any]:
    raw_response = _call_agent(
        agent_id=PROTOCOL_CRITERIA_AGENT_ID,
        session_id=f"{PROTOCOL_CRITERIA_AGENT_ID}-{protocol_id}",
        message=f"Extract eligibility criteria from this protocol:\n\n{protocol_text}",
    )

    try:
        return json.loads(raw_response)
    except json.JSONDecodeError as e:
        raise LyzrAgentError(
            f"Agent did not return valid JSON. Raw response: {raw_response[:500]}"
        ) from e
