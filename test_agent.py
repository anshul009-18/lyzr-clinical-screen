"""
Quick test: send real extracted protocol text to the deployed
Protocol Criteria Agent and check it returns real, non-empty criteria.

Usage:
    export $(grep LYZR_API_KEY .env | xargs)
    python test_agent.py
"""

import os
import requests
import pdfplumber

API_KEY = os.environ.get("LYZR_API_KEY")
if not API_KEY:
    raise SystemExit("LYZR_API_KEY not set — export it from .env first")

AGENT_ID = "6ab108f7c9090433f7a1b4bb"
USER_ID = "ajanshul02@gmail.com"
URL = "https://agent-prod.studio.lyzr.ai/v3/inference/chat/"

# Extract real protocol text
with pdfplumber.open("data/sample_protocols/protocol_001.pdf") as pdf:
    protocol_text = "\n".join(p.extract_text() for p in pdf.pages if p.extract_text())

payload = {
    "user_id": USER_ID,
    "agent_id": AGENT_ID,
    "session_id": f"{AGENT_ID}-test-real",
    "message": f"Extract eligibility criteria from this protocol:\n\n{protocol_text}",
}

response = requests.post(
    URL,
    headers={"Content-Type": "application/json", "x-api-key": API_KEY},
    json=payload,
    timeout=60,
)

print("Status:", response.status_code)
print("Response:")
print(response.json())
