import io
import json

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ingest_patient_json():
    patient = {
        "patient_id": "TEST-JSON-001",
        "age": 45,
        "sex": "female",
        "labs": {"eGFR": 75.0, "HbA1c": 7.5},
        "conditions": ["Type 2 Diabetes Mellitus"],
        "medications": ["Metformin"],
        "pregnant": False,
        "last_glp1_dose_days_ago": 20,
    }
    file_bytes = json.dumps(patient).encode()
    resp = client.post(
        "/ingest/patient",
        files={"file": ("patient_test.json", io.BytesIO(file_bytes), "application/json")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["patient_id"] == "TEST-JSON-001"
    assert data["labs"]["eGFR"] == 75.0

    # confirm it actually persisted, not just returned
    get_resp = client.get("/ingest/patient/TEST-JSON-001")
    assert get_resp.status_code == 200


def test_ingest_patient_text():
    text = (
        "Name: Test Patient\n"
        "DOB: 1990-01-01\n"
        "MRN: MRN-99999\n"
        "Age: 34\n"
        "eGFR: 88\n"
        "HbA1c: 7.2\n"
        "Conditions: Type 2 Diabetes Mellitus\n"
        "Medications: Metformin\n"
    )
    resp = client.post(
        "/ingest/patient",
        files={"file": ("patient_text_test.txt", io.BytesIO(text.encode()), "text/plain")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["patient_id"] == "patient_text_test"  # fallback_id from filename stem
    assert data["labs"]["eGFR"] == 88.0
    assert data["labs"]["HbA1c"] == 7.2
    # PHI fields SHOULD parse correctly at ingestion — scrubbing is a
    # separate, later step (Phase 3). Ingestion's job is accurate parsing.
    assert data["mrn"] == "MRN-99999"
    assert data["name"] == "Test Patient"


def test_ingest_patient_rejects_unsupported_format():
    resp = client.post(
        "/ingest/patient",
        files={"file": ("patient.xyz", io.BytesIO(b"garbage"), "application/octet-stream")},
    )
    assert resp.status_code == 422


def test_ingest_protocol_rejects_non_pdf():
    resp = client.post(
        "/ingest/protocol",
        files={"file": ("not_a_pdf.txt", io.BytesIO(b"plain text protocol"), "text/plain")},
    )
    assert resp.status_code == 400


def test_get_nonexistent_patient_returns_404():
    resp = client.get("/ingest/patient/DOES-NOT-EXIST")
    assert resp.status_code == 404


def test_list_patients_returns_ids():
    # depends on test_ingest_patient_json having run and persisted TEST-JSON-001
    resp = client.get("/ingest/patients")
    assert resp.status_code == 200
    assert "patient_ids" in resp.json()
