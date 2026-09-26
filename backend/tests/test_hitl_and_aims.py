# backend/tests/test_hitl_and_aims.py
"""
Coverage for the two stretch-goal endpoints that have been wired in
but never had a dedicated test: HITL pause-on-low-confidence, and
the AIMS event feed the dashboard reads from.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.hitl_webhook import should_pause_for_review

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = REPO_ROOT / "data" / "sample_protocols" / "protocol_001.pdf"
PATIENT_DIR = REPO_ROOT / "data" / "synthetic_ehr"


@pytest.fixture(scope="module")
def protocol_id():
    with open(PROTOCOL_PATH, "rb") as f:
        client.post("/ingest/protocol", files={"file": ("protocol_001.pdf", f, "application/pdf")})
    with open(PROTOCOL_PATH, "rb") as f:
        resp = client.post("/screen/extract-criteria", files={"file": ("protocol_001.pdf", f, "application/pdf")})
    return resp.json()["protocol_id"]


def _run_one_patient(protocol_id, patient_file):
    patient = json.loads(patient_file.read_text())
    patient_id = patient["patient_id"]
    with open(patient_file, "rb") as f:
        client.post("/ingest/patient", files={"file": (patient_file.name, f, "application/json")})
    resp = client.post("/audit/generate", params={"patient_id": patient_id, "protocol_id": protocol_id})
    assert resp.status_code == 200, resp.text
    return resp.json()


# --------------------------------------------------------------------
# should_pause_for_review — pure logic, no network/DB needed
# --------------------------------------------------------------------

def test_should_pause_below_threshold():
    assert should_pause_for_review("ELIGIBLE", 0.5) is True


def test_should_pause_on_requires_human_review():
    assert should_pause_for_review("REQUIRES_HUMAN_REVIEW", 0.99) is True


def test_should_not_pause_high_confidence_eligible():
    assert should_pause_for_review("ELIGIBLE", 0.97) is False


# --------------------------------------------------------------------
# /audit/generate -> hitl_pending flag, /hitl/pending, /hitl/{id}/resolve
# --------------------------------------------------------------------

def test_generate_audit_reports_hitl_pending_flag(protocol_id):
    patient_file = sorted(PATIENT_DIR.glob("patient_*.json"))[0]
    result = _run_one_patient(protocol_id, patient_file)
    assert "hitl_pending" in result
    assert isinstance(result["hitl_pending"], bool)


def test_hitl_pending_list_reflects_generated_dossiers(protocol_id):
    # run every patient once so at least one is statistically likely
    # to land below the confidence threshold or need human review
    for patient_file in sorted(PATIENT_DIR.glob("patient_*.json")):
        _run_one_patient(protocol_id, patient_file)

    resp = client.get("/hitl/pending")
    assert resp.status_code == 200
    pending = resp.json()["pending"]
    assert isinstance(pending, list)
    # every pending entry should be well-formed if any exist
    for entry in pending:
        assert entry["status"] if "status" in entry else True
        assert "dossier_id" in entry
        assert "confidence" in entry


def test_resolve_nonexistent_hitl_review_404s():
    resp = client.post("/hitl/does-not-exist/resolve", params={"status": "approved"})
    assert resp.status_code == 404


def test_resolve_rejects_invalid_status(protocol_id):
    patient_file = sorted(PATIENT_DIR.glob("patient_*.json"))[1]
    result = _run_one_patient(protocol_id, patient_file)
    resp = client.post(f"/hitl/{result['dossier_id']}/resolve", params={"status": "maybe"})
    assert resp.status_code == 400


# --------------------------------------------------------------------
# /aims/events
# --------------------------------------------------------------------

def test_aims_events_returns_list_after_pipeline_run(protocol_id):
    patient_file = sorted(PATIENT_DIR.glob("patient_*.json"))[2]
    patient = json.loads(patient_file.read_text())
    _run_one_patient(protocol_id, patient_file)

    resp = client.get("/aims/events")
    assert resp.status_code == 200
    body = resp.json()
    assert "events" in body and "total" in body
    assert body["total"] > 0

    # filter by this patient specifically
    resp2 = client.get(f"/aims/events?patient_id={patient['patient_id']}")
    assert resp2.status_code == 200
    patient_events = resp2.json()["events"]
    assert all(e["patient_id"] == patient["patient_id"] for e in patient_events)
    assert len(patient_events) > 0


def test_aims_events_never_contain_raw_phi(protocol_id):
    patient_file = sorted(PATIENT_DIR.glob("patient_*.json"))[3]
    patient = json.loads(patient_file.read_text())
    _run_one_patient(protocol_id, patient_file)

    resp = client.get("/aims/events")
    events_text = json.dumps(resp.json())
    assert patient.get("email", "zzz-none") not in events_text
    assert patient.get("mrn", "zzz-none") not in events_text
