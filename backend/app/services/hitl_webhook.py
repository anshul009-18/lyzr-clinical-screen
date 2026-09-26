"""
Stretch goal — HITL (human-in-the-loop) webhook pause.
Fires whenever a screening run's overall confidence drops below
HITL_CONFIDENCE_THRESHOLD, or the decision itself is already
REQUIRES_HUMAN_REVIEW — whichever triggers first. This never expands
what Screening/Medical Safety already decided; it only adds a pause
+ notification layer on top of an existing dossier.

Same PHI discipline as every other outbound call in this codebase:
the payload is built from screening metadata only (decision,
confidence, dossier_id, protocol_id, patient_id — patient_id is
already a synthetic study ID, never a real identifier) and is
re-scanned before send, refusing to fire rather than redact-and-send.
"""

import os
import requests

from agents.phi_scrubbing_agent.safe_ai_rules import scan_blob_for_phi

HITL_WEBHOOK_URL = os.environ.get("HITL_WEBHOOK_URL")
HITL_CONFIDENCE_THRESHOLD = float(os.environ.get("HITL_CONFIDENCE_THRESHOLD", "0.90"))


class HITLWebhookError(Exception):
    pass


def should_pause_for_review(decision: str, confidence: float) -> bool:
    return confidence < HITL_CONFIDENCE_THRESHOLD or decision == "REQUIRES_HUMAN_REVIEW"


def trigger_hitl_pause(
    dossier_id: str, patient_id: str, protocol_id: str,
    decision: str, confidence: float, reason: str | None,
) -> None:
    """
    Sends a pause notification. Local-only (recorded via
    backend/app/db/storage.py::save_hitl_review) if HITL_WEBHOOK_URL
    isn't configured — same dev-mode fallback pattern as
    aims_stream.py::stream_event.
    """
    payload = {
        "dossier_id": dossier_id,
        "patient_id": patient_id,   # synthetic study ID, not PHI
        "protocol_id": protocol_id,
        "decision": decision,
        "confidence": confidence,
        "reason": reason or f"Confidence {confidence:.2f} below threshold {HITL_CONFIDENCE_THRESHOLD:.2f}",
    }

    blob = " ".join(str(v) for v in payload.values())
    hits = scan_blob_for_phi(blob)
    if hits:
        raise HITLWebhookError(f"Refused to fire HITL webhook for {dossier_id} — PHI detected: {hits}")

    if not HITL_WEBHOOK_URL:
        return  # dev mode — pause is recorded in storage only, no live webhook call

    resp = requests.post(HITL_WEBHOOK_URL, json=payload, timeout=15)
    resp.raise_for_status()
