"""
Phase 3/4 — Lyzr AIMS event streaming.
Every AuditEvent from PipelineState.log_event() streams here. Same rule
as backend logs: no raw PHI reaches AIMS, verified independently — so
AIMS streaming can never become the one code path that skips the check.
"""

import os
import requests

from agents.phi_scrubbing_agent.safe_ai_rules import scan_blob_for_phi

LYZR_AIMS_ENDPOINT = os.environ.get("LYZR_AIMS_ENDPOINT")

_LOCAL_EVENT_LOG: list[dict] = []  # always populated — audit trail even without live AIMS


class AIMSStreamError(Exception):
    pass


def stream_event(patient_id: str, step: str, detail: str) -> None:
    """
    Sends one pipeline event to AIMS. Re-scans `detail` for PHI
    immediately before send — refuses to stream rather than
    redact-and-send, since a trace record is meant to be an exact
    account of what happened.
    """
    regex_hits = scan_blob_for_phi(detail)
    if regex_hits:
        raise AIMSStreamError(
            f"[{patient_id}] Refused to stream '{step}' to AIMS — "
            f"PHI detected: regex={regex_hits}"
        )

    payload = {"patient_id": patient_id, "step": step, "detail": detail}
    _LOCAL_EVENT_LOG.append(payload)

    if not LYZR_AIMS_ENDPOINT:
        return  # dev mode — local log only

    resp = requests.post(LYZR_AIMS_ENDPOINT, json=payload, timeout=15)
    resp.raise_for_status()


def get_local_event_log() -> list[dict]:
    """
    Audit accessor for backend/tests/test_audit.py — confirms the full
    local trail is PHI-free without needing live AIMS access.
    """
    return list(_LOCAL_EVENT_LOG)
