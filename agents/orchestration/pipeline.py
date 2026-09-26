"""
Phase 3/4 orchestration.
Lyzr triad discipline: Environment / Agent / Inference stay separated
here — backend/ never calls an LLM directly, only through this module.

PHI scrubbing is a hard gate: Screening and Medical Safety are
unreachable unless PipelineState.phi_status == SCRUBBED. No bypass
flag, no "trusted caller" path, no optional=True — enforced in code,
not by caller discipline.
"""

import json as _json

from agents.orchestration.state import PipelineState, PHIStatus
from agents.phi_scrubbing_agent.safe_ai_rules import (
    redact_direct_identifiers,
    scan_for_leaked_phi,
    scan_blob_for_phi,
)


class PHIGateError(Exception):
    """Raised when a record fails the PHI scrub gate. Pipeline halts — never proceeds silently."""


def run_phi_scrub(state: PipelineState) -> PipelineState:
    """
    Mandatory Phase 3 step. Deterministic regex-based redaction — see
    safe_ai_rules.py docstring for why there's no live Safe AI network call.
    """
    if state.raw_patient_record is None:
        raise PHIGateError(f"[{state.patient_id}] No raw_patient_record to scrub")

    record = redact_direct_identifiers(state.raw_patient_record)
    state.log_event("phi_scrub", "Direct identifiers redacted (regex/rule-based)")

    leaked = scan_for_leaked_phi(record)
    if leaked:
        state.phi_status = PHIStatus.SCRUB_FAILED
        state.log_event("phi_scrub", f"Post-scrub re-scan found residual PHI: {leaked}")
        raise PHIGateError(f"[{state.patient_id}] Residual PHI detected after scrub: {leaked}")

    state.scrubbed_patient_record = record
    state.phi_status = PHIStatus.SCRUBBED
    state.log_event("phi_scrub", "Record scrubbed and verified clean")
    return state


def _require_scrubbed(state: PipelineState) -> None:
    """Internal guard. Every downstream agent call goes through this first — not exported, no bypass."""
    if state.phi_status != PHIStatus.SCRUBBED:
        raise PHIGateError(
            f"[{state.patient_id}] Blocked: phi_status={state.phi_status.value}, "
            f"must be SCRUBBED before Screening/Medical Safety agents run"
        )
    if state.scrubbed_patient_record is None:
        raise PHIGateError(f"[{state.patient_id}] Blocked: phi_status SCRUBBED but scrubbed_patient_record is empty")


def run_screening(state: PipelineState) -> PipelineState:
    """Phase 4a entrypoint — gated. Local import so an unbuilt matcher.py doesn't break Phase 3."""
    _require_scrubbed(state)
    from agents.screening_agent.matcher import evaluate_patient  # Phase 4
    state.screening_result = evaluate_patient(state.scrubbed_patient_record, state.extracted_criteria)
    state.log_event("screening", f"Decision: {state.screening_result.decision.value}")
    return state


def run_medical_safety(state: PipelineState) -> PipelineState:
    """Phase 4b entrypoint — gated. Same import-guard reasoning as run_screening."""
    _require_scrubbed(state)
    from agents.medical_safety_agent.ontology_validator import validate  # Phase 4
    flagged, reason = validate(state.scrubbed_patient_record)
    state.screening_result.flagged_by_medical_safety = flagged
    state.screening_result.flag_reason = reason
    state.log_event("medical_safety", f"Flagged: {flagged}" + (f" — {reason}" if reason else ""))
    return state


def run_pipeline(state: PipelineState) -> PipelineState:
    """
    Fixed order: PHI scrub -> screening -> medical safety. The latter two
    are unreachable without a clean scrub (_require_scrubbed), not merely
    called in this sequence by convention.
    """
    run_phi_scrub(state)
    run_screening(state)
    run_medical_safety(state)
    return state


def verify_before_persist(payload, context: str, state: PipelineState) -> None:
    """
    Redaction verification gate. Re-scans ANY payload immediately before
    it is written anywhere durable. Regex-based — see safe_ai_rules.py.
    """
    blob = payload if isinstance(payload, str) else _json.dumps(payload, default=str)
    regex_hits = scan_blob_for_phi(blob)

    if regex_hits:
        state.log_event("redaction_verification", f"BLOCKED persist of '{context}' — regex: {regex_hits}")
        raise PHIGateError(f"[{state.patient_id}] Verification failed for '{context}': regex hits={regex_hits}")

    state.log_event("redaction_verification", f"'{context}' verified clean — persisted")


def persist_patient_record(state: PipelineState) -> None:
    """Only path allowed to write pipeline patient data to storage — never call storage.save_patient directly on pipeline output."""
    from backend.app.db import storage
    verify_before_persist(state.scrubbed_patient_record, "scrubbed_patient_record", state)
    storage.save_patient(state.patient_id, state.scrubbed_patient_record)


def persist_screening_result(state: PipelineState) -> None:
    """Same pattern for the screening result — AIMS wiring lands in Phase 4."""
    verify_before_persist(state.screening_result.model_dump(), "screening_result", state)
