import logging
import pytest

from agents.orchestration.state import PipelineState, PHIStatus
from agents.orchestration.pipeline import run_phi_scrub, PHIGateError
from backend.app.logging_config import PHIRedactionFilter, audit_log_line
from backend.app.services.aims_stream import stream_event, get_local_event_log, AIMSStreamError

CLEAN_PATIENT = {
    "patient_id": "test-001", "name": "Jane Doe", "dob": "04/12/1985",
    "mrn": "MRN: 88213", "address": "12 Elm St", "phone": "555-123-4567",
    "email": "jane.doe@example.com",
    "conditions": ["Type 2 diabetes"], "medications": ["metformin"],
}

LEAKY_PATIENT = {
    **CLEAN_PATIENT,
    "conditions": ["Type 2 diabetes, contact jane.doe@example.com for records"],
}


def test_scrubbed_record_has_no_raw_identifiers():
    state = PipelineState(patient_id="test-001", protocol_id="protocol_001")
    state.raw_patient_record = dict(CLEAN_PATIENT)
    run_phi_scrub(state)

    assert state.phi_status == PHIStatus.SCRUBBED
    for field in ("name", "dob", "mrn", "address", "phone", "email"):
        assert state.scrubbed_patient_record[field] is None


def test_scrub_blocks_on_leaked_free_text_phi():
    """The gate's whole job is to catch this — a passing scrub here would be the bug."""
    state = PipelineState(patient_id="test-002", protocol_id="protocol_001")
    state.raw_patient_record = dict(LEAKY_PATIENT)
    with pytest.raises(PHIGateError, match="Residual PHI"):
        run_phi_scrub(state)
    assert state.phi_status == PHIStatus.SCRUB_FAILED


def test_logging_filter_redacts_structured_phi():
    """Regex layer's actual scope: emails, phones, MRNs, dates, title-prefixed
    names. Bare names are NOT covered here — direct_id_fields being nulled
    upstream is what prevents those from ever reaching a log line."""
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Ingested patient, MRN: 88213, contact jane.doe@example.com, phone 555-123-4567",
        args=(), exc_info=None,
    )
    PHIRedactionFilter().filter(record)
    final_message = record.getMessage()

    assert "jane.doe@example.com" not in final_message
    assert "555-123-4567" not in final_message
    assert audit_log_line(final_message) == []


def test_aims_stream_refuses_structured_phi_in_event():
    with pytest.raises(AIMSStreamError):
        stream_event("test-001", "ingestion", "Loaded record, contact jane.doe@example.com")


def test_aims_stream_accepts_clean_event_and_logs_it():
    stream_event("test-001", "phi_scrub", "Record scrubbed and verified clean")
    log = get_local_event_log()
    assert log[-1]["detail"] == "Record scrubbed and verified clean"
    assert audit_log_line(log[-1]["detail"]) == []
